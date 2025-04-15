import os
import re
import gc
import yt_dlp
import threading
import platform
import datetime
import subprocess
import tkinter as tk
import json
from tkinter import ttk
from tkinter import filedialog, messagebox, scrolledtext
from pathlib import Path
from functools import partial
import tkinter.font as tkfont

class YouTubeDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Downloader")
        self.root.geometry("550x750")
        self.root.minsize(500, 700)
        
        # Variables
        self.selected_quality = "720p"
        self.download_thread = None
        self.stop_download = False
        self.download_history = []
        self.download_queue = []
        self.is_downloading = False
        self.current_video_info = None
        self.max_history_items = 50
        self.history_visible = False
        self.history_frame = None
        
        # Theme variables
        self.is_dark_mode = False
        
        # Define colors for themes
        self.theme_colors = {
            "light": {
                "bg": "#f5f5f7",
                "card_bg": "white",
                "text": "black",
                "button_bg": "#e0e0e0",
                "progress_bg": "#33b249",
                "progress_trough": "#f0f0f0"
            },
            "dark": {
                "bg": "#2d2d30",
                "card_bg": "#3e3e42",
                "text": "white",
                "button_bg": "#505050",
                "progress_bg": "#33b249",
                "progress_trough": "#1e1e1e"
            }
        }
        
        # Styles
        self.style = ttk.Style()
        self.configure_styles()
        
        # Main Frame with Canvas and Scrollbar
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Canvas for scrolling
        self.canvas = tk.Canvas(self.main_frame, bg=self.theme_colors["light"]["bg"])
        self.scrollbar = ttk.Scrollbar(self.main_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Frame inside canvas for UI components
        self.content_frame = ttk.Frame(self.canvas, padding=20)
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.content_frame, anchor="nw")
        
        # Configure canvas scrolling
        self.content_frame.bind("<Configure>", self.configure_scroll_region)
        self.canvas.bind("<Configure>", self.configure_canvas_width)
        
        # Create UI Components
        self.create_header_card()
        self.create_url_input_card()
        self.create_progress_card()  # Move this up before create_quality_selection_card
        self.create_quality_selection_card()
        
        # Configure mouse wheel scrolling
        self.root.bind("<MouseWheel>", self.on_mousewheel)
        # For Linux and macOS
        self.root.bind("<Button-4>", self.on_mousewheel)
        self.root.bind("<Button-5>", self.on_mousewheel)
        
        # Load saved history
        self.load_history()
    
    def configure_styles(self):
        """Configure the styles based on current theme"""
        theme = "dark" if self.is_dark_mode else "light"
        colors = self.theme_colors[theme]
        
        bg_color = colors["bg"]
        card_bg = colors["card_bg"]
        text_color = colors["text"]
        button_bg = colors["button_bg"]
        
        self.style.configure('TFrame', background=bg_color)
        self.style.configure('TButton', font=('Arial', 10, 'bold'), background=button_bg, foreground=text_color)
        self.style.configure('TLabel', font=('Arial', 10), background=card_bg, foreground=text_color)
        self.style.configure('Header.TLabel', font=('Arial', 18, 'bold'), background=card_bg, foreground=text_color)
        self.style.configure('Subheader.TLabel', font=('Arial', 10), background=card_bg, foreground=text_color)
        self.style.configure('Card.TFrame', background=card_bg, relief='raised', borderwidth=2)
        self.style.configure('GreenButton.TButton', background='#33b249')
        self.style.configure('RedButton.TButton', background='#cc3333')
        self.style.configure('BlueButton.TButton', background='#6666e6')
        self.style.configure('QualityButton.TButton', width=10, padding=5, background=button_bg)
        self.style.configure('Horizontal.TProgressbar', 
                            thickness=8, 
                            background=colors["progress_bg"], 
                            troughcolor=colors["progress_trough"])
        
        # Configure entries
        self.style.configure('TEntry', fieldbackground=card_bg, foreground=text_color)
        
        # Configure the listbox style (will be created dynamically)
        self.style.configure('History.TFrame', background=card_bg)
    
    def on_mousewheel(self, event):
        if event.num == 4:  # Linux scroll up
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:  # Linux scroll down
            self.canvas.yview_scroll(1, "units")
        else:  # Windows
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def configure_scroll_region(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def configure_canvas_width(self, event):
        self.canvas.itemconfig(self.canvas_frame, width=event.width)
    
    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        theme = "dark" if self.is_dark_mode else "light"
        colors = self.theme_colors[theme]
        
        # Update canvas and root background
        self.canvas.configure(bg=colors["bg"])
        self.root.configure(bg=colors["bg"])
        
        # Reconfigure all styles
        self.configure_styles()
        
        # Update all existing widgets
        self.update_widget_styles(self.content_frame)
        
        # Update history frame if visible
        if self.history_visible and self.history_frame:
            self.update_widget_styles(self.history_frame)
    
    def update_widget_styles(self, parent):
        """Recursively update all widget styles"""
        for widget in parent.winfo_children():
            widget_type = widget.winfo_class()
            
            if widget_type == "TFrame":
                if "card" in str(widget).lower():
                    widget.configure(style="Card.TFrame")
                else:
                    widget.configure(style="TFrame")
            elif widget_type == "TLabel":
                if "header" in str(widget).lower():
                    widget.configure(style="Header.TLabel")
                elif "subheader" in str(widget).lower():
                    widget.configure(style="Subheader.TLabel")
                else:
                    widget.configure(style="TLabel")
            elif widget_type == "TButton":
                # Preserve special button styles
                if "download" in str(widget).lower():
                    widget.configure(style="GreenButton.TButton")
                elif "cancel" in str(widget).lower():
                    widget.configure(style="RedButton.TButton")
                elif "history" in str(widget).lower():
                    widget.configure(style="BlueButton.TButton")
                elif any(quality in str(widget).lower() for quality in ["360p", "480p", "720p", "1080p", "2k", "4k", "best", "audio"]):
                    widget.configure(style="QualityButton.TButton")
                else:
                    widget.configure(style="TButton")
            elif widget_type == "TProgressbar":
                widget.configure(style="Horizontal.TProgressbar")
            elif widget_type == "TEntry":
                widget.configure(style="TEntry")
            elif widget_type == "Listbox":
                theme = "dark" if self.is_dark_mode else "light"
                colors = self.theme_colors[theme]
                widget.configure(bg=colors["card_bg"], fg=colors["text"])
            
            # Recursively update child widgets
            if hasattr(widget, 'winfo_children'):
                self.update_widget_styles(widget)
    
    def create_header_card(self):
        header_card = ttk.Frame(self.content_frame, style='Card.TFrame', padding=15)
        header_card.pack(fill=tk.X, pady=10)
        
        header_container = ttk.Frame(header_card, style='Card.TFrame')
        header_container.pack(fill=tk.X)
        
        header_label = ttk.Label(header_container, text="YouTube Downloader", style='Header.TLabel')
        header_label.pack(side=tk.LEFT, expand=True)
        
        theme_button = ttk.Button(header_container, text="🌓", width=3, 
                                 command=self.toggle_theme)
        theme_button.pack(side=tk.RIGHT)
        
        subheader = ttk.Label(header_card, text="Download videos and audio with ease", 
                             style='Subheader.TLabel')
        subheader.pack(pady=(5, 0))
    
    def create_url_input_card(self):
        url_card = ttk.Frame(self.content_frame, style='Card.TFrame', padding=15)
        url_card.pack(fill=tk.X, pady=10)
        
        # URL input
        url_frame = ttk.Frame(url_card, style='Card.TFrame')
        url_frame.pack(fill=tk.X, pady=5)
        
        self.url_input = ttk.Entry(url_frame)
        self.url_input.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)
        
        url_button = ttk.Button(url_frame, text="Preview", command=self.preview_video)
        url_button.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Folder input
        folder_frame = ttk.Frame(url_card, style='Card.TFrame')
        folder_frame.pack(fill=tk.X, pady=5)
        
        self.folder_input = ttk.Entry(folder_frame)
        self.folder_input.insert(0, self.get_default_download_folder())
        self.folder_input.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)
        
        browse_button = ttk.Button(folder_frame, text="Browse", command=self.browse_folder)
        browse_button.pack(side=tk.RIGHT, padx=(5, 0))
    
    def create_quality_selection_card(self):
        quality_card = ttk.Frame(self.content_frame, style='Card.TFrame', padding=15)
        quality_card.pack(fill=tk.X, pady=10)
        
        quality_label = ttk.Label(quality_card, text="Select Quality",
                                 font=('Arial', 12, 'bold'), style='TLabel')
        quality_label.pack(anchor='w', pady=(0, 10))
        
        # Quality buttons in grid
        quality_frame = ttk.Frame(quality_card, style='Card.TFrame')
        quality_frame.pack(fill=tk.X)
        
        # Row 1
        row1 = ttk.Frame(quality_frame, style='Card.TFrame')
        row1.pack(fill=tk.X, pady=5)
        
        self.btn_360p = ttk.Button(row1, text="360p", style='QualityButton.TButton',
                                 command=lambda: self.set_quality("360p"))
        self.btn_360p.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.btn_480p = ttk.Button(row1, text="480p", style='QualityButton.TButton',
                                  command=lambda: self.set_quality("480p"))
        self.btn_480p.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.btn_720p = ttk.Button(row1, text="720p", style='QualityButton.TButton',
                                 command=lambda: self.set_quality("720p"))
        self.btn_720p.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Row 2
        row2 = ttk.Frame(quality_frame, style='Card.TFrame')
        row2.pack(fill=tk.X, pady=5)
        
        self.btn_1080p = ttk.Button(row2, text="1080p", style='QualityButton.TButton',
                                   command=lambda: self.set_quality("1080p"))
        self.btn_1080p.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.btn_2k = ttk.Button(row2, text="2K", style='QualityButton.TButton',
                               command=lambda: self.set_quality("1440"))
        self.btn_2k.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.btn_4k = ttk.Button(row2, text="4K", style='QualityButton.TButton',
                               command=lambda: self.set_quality("2160"))
        self.btn_4k.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Row 3
        row3 = ttk.Frame(quality_frame, style='Card.TFrame')
        row3.pack(fill=tk.X, pady=5)
        
        self.btn_best = ttk.Button(row3, text="Best Quality", style='QualityButton.TButton',
                                  command=lambda: self.set_quality("best"))
        self.btn_best.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.btn_audio = ttk.Button(row3, text="Audio Only", style='QualityButton.TButton',
                                   command=lambda: self.set_quality("audio"))
        self.btn_audio.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Highlight default selected quality
        self.set_quality("720p")
    
    def create_progress_card(self):
        progress_card = ttk.Frame(self.content_frame, style='Card.TFrame', padding=15)
        progress_card.pack(fill=tk.X, pady=10)
        
        # Progress label
        self.progress_label = ttk.Label(progress_card, text="Ready to download",
                                       wraplength=450, justify='center', style='TLabel')
        self.progress_label.pack(fill=tk.X, pady=10, ipady=10)
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(progress_card, style='Horizontal.TProgressbar',
                                          orient='horizontal', length=100, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=10)
        
        # Buttons
        buttons_frame = ttk.Frame(progress_card, style='Card.TFrame')
        buttons_frame.pack(fill=tk.X, pady=10)
        
        self.download_button = ttk.Button(buttons_frame, text="DOWNLOAD",
                                        command=self.start_download, style='GreenButton.TButton')
        self.download_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.cancel_button = ttk.Button(buttons_frame, text="CANCEL",
                                       command=self.cancel_download, style='RedButton.TButton')
        self.cancel_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.history_button = ttk.Button(buttons_frame, text="HISTORY",
                                        command=self.toggle_history, style='BlueButton.TButton')
        self.history_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
    
    def create_history_card(self):
        if self.history_frame:
            self.history_frame.destroy()
        
        self.history_frame = ttk.Frame(self.content_frame, style='Card.TFrame', padding=15)
        self.history_frame.pack(fill=tk.X, pady=10)
        
        # Header with title and close button
        header_frame = ttk.Frame(self.history_frame, style='Card.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        history_label = ttk.Label(header_frame, text="Download History", 
                                 font=('Arial', 12, 'bold'), style='TLabel')
        history_label.pack(side=tk.LEFT)
        
        clear_button = ttk.Button(header_frame, text="Clear", 
                                 command=self.clear_history, width=8)
        clear_button.pack(side=tk.RIGHT, padx=5)
        
        # Create a scrollable area for history items
        history_container = ttk.Frame(self.history_frame, style='History.TFrame')
        history_container.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create a canvas with scrollbar for the history items
        history_canvas = tk.Canvas(history_container, 
                                  bg=self.theme_colors["dark" if self.is_dark_mode else "light"]["card_bg"],
                                  highlightthickness=0)
        history_scrollbar = ttk.Scrollbar(history_container, orient=tk.VERTICAL, 
                                         command=history_canvas.yview)
        
        history_canvas.configure(yscrollcommand=history_scrollbar.set)
        history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        history_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Frame for history items
        items_frame = ttk.Frame(history_canvas, style='History.TFrame')
        history_canvas.create_window((0, 0), window=items_frame, anchor="nw")
        
        # Add history items
        if not self.download_history:
            no_history_label = ttk.Label(items_frame, text="No download history yet", 
                                        style='TLabel', padding=10)
            no_history_label.pack(fill=tk.X)
        else:
            for i, item in enumerate(self.download_history):
                self.create_history_item(items_frame, item, i)
        
        # Configure canvas
        items_frame.bind("<Configure>", 
                       lambda e: history_canvas.configure(scrollregion=history_canvas.bbox("all")))
        history_canvas.bind("<Configure>", 
                          lambda e: history_canvas.itemconfig(history_canvas.find_withtag("all")[0], 
                                                           width=e.width))
    
    def create_history_item(self, parent, item, index):
        item_frame = ttk.Frame(parent, style='History.TFrame', padding=5)
        item_frame.pack(fill=tk.X, pady=2)
        
        # Add a separator before each item (except the first one)
        if index > 0:
            separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
            separator.pack(fill=tk.X, pady=5)
        
        # Status icon
        status = "✅" if item.get('success', False) else "❌"
        
        # Title with status
        title = item.get('title', 'Unknown')
        title_text = f"{status} {title}"
        
        title_label = ttk.Label(item_frame, text=title_text, wraplength=450,
                               style='TLabel', font=('Arial', 10, 'bold'))
        title_label.pack(anchor='w')
        
        # Details
        quality = item.get('quality', 'Unknown')
        timestamp = item.get('timestamp', 'Unknown')
        
        details_text = f"Quality: {quality} | {timestamp}"
        details_label = ttk.Label(item_frame, text=details_text, 
                                style='TLabel', font=('Arial', 9))
        details_label.pack(anchor='w')
        
        # URL (optional)
        if item.get('url'):
            url = item.get('url')
            url_label = ttk.Label(item_frame, text=f"URL: {url}", 
                                style='TLabel', font=('Arial', 8), foreground='gray')
            url_label.pack(anchor='w')
    
    def toggle_history(self):
        self.history_visible = not self.history_visible
        
        if self.history_visible:
            self.create_history_card()
            self.history_button.configure(text="HIDE HISTORY")
        else:
            if self.history_frame:
                self.history_frame.destroy()
                self.history_frame = None
            self.history_button.configure(text="HISTORY")
    
    def get_default_download_folder(self):
        try:
            downloads_dir = Path.home() / "Downloads"
            # Create the directory if it doesn't exist
            if not downloads_dir.exists():
                downloads_dir.mkdir(parents=True, exist_ok=True)
            return str(downloads_dir)
        except Exception:
            # Fallback to current directory if home directory isn't accessible
            return os.path.abspath(".")
    
    def browse_folder(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.folder_input.delete(0, tk.END)
            self.folder_input.insert(0, folder_path)
    
    def set_quality(self, quality):
        self.selected_quality = quality
        self.progress_label.config(text=f"Selected Quality: {quality}")
        
        # Reset all button styles
        for btn in [self.btn_360p, self.btn_480p, self.btn_720p, 
                    self.btn_1080p, self.btn_2k, self.btn_4k, 
                    self.btn_best, self.btn_audio]:
            btn.configure(style='QualityButton.TButton')
        
        # Highlight selected button
        button_map = {
            "360p": self.btn_360p,
            "480p": self.btn_480p,
            "720p": self.btn_720p,
            "1080p": self.btn_1080p,
            "1440": self.btn_2k,
            "2160": self.btn_4k,
            "best": self.btn_best,
            "audio": self.btn_audio
        }
        
        if quality in button_map:
            # Create a new style for the selected button
            selected_style = f'Selected{quality}.TButton'
            theme = "dark" if self.is_dark_mode else "light"
            self.style.configure(selected_style, background='#19cc33')
            button_map[quality].configure(style=selected_style)
    
    def preview_video(self):
        url = self.url_input.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a YouTube URL")
            return
        
        # Validate URL
        if not self.is_valid_youtube_url(url):
            messagebox.showerror("Error", "Invalid YouTube URL")
            return
        
        self.progress_label.config(text="Getting video information...")
        
        # Start thread to fetch video information
        threading.Thread(target=self.fetch_video_info, daemon=True).start()
    
    def fetch_video_info(self):
        url = self.url_input.get().strip()
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'no_color': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
            if info:
                self.current_video_info = info
                self.root.after(0, lambda: self.update_ui_with_video_info(info))
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", "Could not fetch video information"))
                
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error: {str(e)}"))
    
    def update_ui_with_video_info(self, info):
        title = info.get('title', 'Unknown')
        duration = info.get('duration', 0)
        duration_str = str(datetime.timedelta(seconds=duration)) if duration else "Unknown"
        
        self.progress_label.config(text=f"Video: {title}\nDuration: {duration_str}\nReady to download")
        
        # Suggest quality based on available formats
        available_formats = set()
        for f in info.get('formats', []):
            if f.get('height'):
                available_formats.add(str(f.get('height')))
        
        # Auto-select a reasonable quality based on available formats
        if '720' in available_formats:
            self.set_quality('720p')
        elif '480' in available_formats:
            self.set_quality('480p')
        elif '1080' in available_formats:
            self.set_quality('1080p')
        else:
            self.set_quality('best')
    
    def is_valid_youtube_url(self, url):
        # Simple validation for YouTube URLs
        youtube_pattern = r'^(https?://)?(www\.)?(youtube\.com|youtu\.?be)/.+$'
        return bool(re.match(youtube_pattern, url))
    
    def start_download(self):
        url = self.url_input.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a YouTube URL")
            return
        
        # Validate URL
        if not self.is_valid_youtube_url(url):
            messagebox.showerror("Error", "Invalid YouTube URL")
            return
        
        download_folder = self.folder_input.get().strip()
        if not download_folder:
            download_folder = self.get_default_download_folder()
            self.folder_input.delete(0, tk.END)
            self.folder_input.insert(0, download_folder)
        
        # Check if the folder exists
        if not os.path.exists(download_folder):
            try:
                os.makedirs(download_folder)
            except Exception as e:
                messagebox.showerror("Error", f"Could not create download folder: {str(e)}")
                return
        
        # Create download task
        task = {
            'url': url,
            'quality': self.selected_quality,
            'download_folder': download_folder,
        }
        
        # Add to queue
        self.download_queue.append(task)
        
        # Start download if not already downloading
        if not self.is_downloading:
            self.process_download_queue()
    
    def process_download_queue(self):
        if not self.download_queue:
            self.is_downloading = False
            return
        self.is_downloading = True
        task = self.download_queue.pop(0)  # Remove task from queue
    
        # Set up download thread
        self.stop_download = False
        self.progress_bar['value'] = 0
        self.progress_label.config(text="Preparing download...")
    
        self.download_thread = threading.Thread(
           target=self.download_video,
           args=(task['url'], task['quality'], task['download_folder']),
           daemon=True
        )
        self.download_thread.start()
    
    def download_video(self, url, quality, download_folder):
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'progress_hooks': [self.progress_hook],
                'outtmpl': os.path.join(download_folder, '%(title)s.%(ext)s')
            }
            
            if quality == 'audio':
                ydl_opts['format'] = 'bestaudio'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            elif quality == 'best':
                ydl_opts['format'] = 'bestvideo+bestaudio/best'
                ydl_opts['merge_output_format'] = 'mp4'
            elif quality in ['360p', '480p', '720p', '1080p'] or quality in ['1440', '2160']:
                height = quality.replace('p', '')
                ydl_opts['format'] = f'bestvideo[height<={height}]+bestaudio/best[height<={height}]'
                ydl_opts['merge_output_format'] = 'mp4'
            else:
                ydl_opts['format'] = 'bestvideo[height<=720]+bestaudio/best[height<=720]'
                ydl_opts['merge_output_format'] = 'mp4'
        
            # Check if download should be stopped before beginning
            if self.stop_download:
                self.root.after(0, lambda: self.update_progress(0, "Download cancelled"))
                return
                
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info:
                    history_item = {
                        'title': info.get('title', 'Unknown'),
                        'quality': quality,
                        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'url': url,
                        'success': True,
                    }
                    self.add_to_history(history_item)
                    
                    # Update history display if visible
                    # Update history display if visible
                    if self.history_visible:
                        self.root.after(0, lambda: self.update_history_display())
                        
                    # If the download is successful, process the next item in queue
                    self.root.after(0, lambda: self.update_progress(100, f"Download complete: {info.get('title', 'Video')}"))
                    
        except Exception as e:
            history_item = {
                'title': self.current_video_info.get('title', 'Unknown') if self.current_video_info else 'Unknown',
                'quality': quality,
                'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'url': url,
                'success': False,
            }
            self.add_to_history(history_item)
            
            if self.history_visible:
                self.root.after(0, lambda: self.update_history_display())
            
            self.root.after(0, lambda: self.update_progress(0, f"Error: {str(e)}"))
        
        finally:
            # Process next download in queue
            gc.collect()  # Force garbage collection
            self.root.after(0, self.process_download_queue)
    
    def progress_hook(self, d):
        if d['status'] == 'downloading':
            p = d.get('_percent_str', '0%')
            p = p.replace('%', '').strip()
            try:
                progress = float(p)
                self.root.after(0, lambda: self.update_progress(progress, f"Downloading: {d.get('_eta_str', '')} remaining"))
            except (ValueError, TypeError):
                pass
        
        elif d['status'] == 'finished':
            self.root.after(0, lambda: self.update_progress(100, "Processing..."))
        
        # Check if download should be stopped
        if self.stop_download:
            raise Exception("Download cancelled by user")
    
    def update_progress(self, progress, status_text):
        self.progress_bar['value'] = progress
        self.progress_label.config(text=status_text)
    
    def cancel_download(self):
        if self.download_thread and self.download_thread.is_alive():
            self.stop_download = True
            self.progress_label.config(text="Cancelling download...")
        else:
            # Clear the queue if no active download
            self.download_queue = []
            self.progress_label.config(text="Ready to download")
    
    def add_to_history(self, item):
        # Add to the beginning of the list
        self.download_history.insert(0, item)
        
        # Limit history size
        if len(self.download_history) > self.max_history_items:
            self.download_history = self.download_history[:self.max_history_items]
            
        # Save history to file
        self.save_history()
    
    def update_history_display(self):
        if self.history_visible:
            self.create_history_card()
    
    def save_history(self):
        try:
            history_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "download_history.json")
            with open(history_file, 'w') as f:
                json.dump(self.download_history, f)
        except Exception:
            # Silently fail if we can't save history
            pass
    
    def load_history(self):
        try:
            history_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "download_history.json")
            if os.path.exists(history_file):
                with open(history_file, 'r') as f:
                    self.download_history = json.load(f)
        except Exception:
            # If we can't load history, start with empty history
            self.download_history = []
    
    def clear_history(self):
        if messagebox.askyesno("Clear History", "Are you sure you want to clear download history?"):
            self.download_history = []
            self.save_history()
            self.update_history_display()

def main():
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
