#!/usr/bin/env python3
"""
Slideshow Builder CLI - Interactive tool to create vitrine slideshows
Usage: python3 slideshow_builder.py [--config vitrine_config.json]
"""

import json
import os
import sys
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}  {text}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.END}\n")

def print_menu(options: List[str], title: str = "Choose an option:"):
    print(f"\n{Colors.CYAN}{title}{Colors.END}")
    for i, opt in enumerate(options, 1):
        print(f"  {Colors.YELLOW}{i}.{Colors.END} {opt}")
    print(f"  {Colors.YELLOW}0.{Colors.END} Cancel / Back")

def get_choice(max_val: int) -> int:
    while True:
        try:
            choice = input(f"\n{Colors.GREEN}Your choice: {Colors.END}").strip()
            if choice == '':
                return 0
            val = int(choice)
            if 0 <= val <= max_val:
                return val
            print(f"{Colors.RED}Please enter a number between 0 and {max_val}{Colors.END}")
        except ValueError:
            print(f"{Colors.RED}Invalid input. Please enter a number.{Colors.END}")

def get_input(prompt: str, default: str = "", required: bool = True) -> str:
    default_str = f" [{default}]" if default else ""
    while True:
        value = input(f"{Colors.CYAN}{prompt}{default_str}: {Colors.END}").strip()
        if value == '' and default:
            return default
        if value == '' and required:
            print(f"{Colors.RED}This field is required.{Colors.END}")
            continue
        return value

def get_yes_no(prompt: str, default: bool = True) -> bool:
    default_str = "Y/n" if default else "y/N"
    while True:
        value = input(f"{Colors.CYAN}{prompt} [{default_str}]: {Colors.END}").strip().lower()
        if value == '':
            return default
        if value in ('y', 'yes', 'o', 'oui'):
            return True
        if value in ('n', 'no', 'non'):
            return False
        print(f"{Colors.RED}Please enter y or n{Colors.END}")

def get_number(prompt: str, default: int = 10, min_val: int = 1, max_val: int = 300) -> int:
    while True:
        value = input(f"{Colors.CYAN}{prompt} [{default}]: {Colors.END}").strip()
        if value == '':
            return default
        try:
            num = int(value)
            if min_val <= num <= max_val:
                return num
            print(f"{Colors.RED}Please enter a number between {min_val} and {max_val}{Colors.END}")
        except ValueError:
            print(f"{Colors.RED}Invalid number{Colors.END}")

def generate_id(title: str) -> str:
    """Generate a slug ID from title"""
    import re
    # Remove emojis and special chars
    clean = re.sub(r'[^\w\s-]', '', title.lower())
    return re.sub(r'[\s_]+', '-', clean).strip('-')[:20]

class SlideBuilder:
    SLIDE_TYPES = {
        'title': 'Title Slide (big title + subtitle)',
        'text': 'Text Slide (title + content + icon)',
        'image': 'Image Slide (title + image + caption)',
        'video': 'Video Slide (title + video)',
        'offer': 'Offer/Pricing Slide (price + benefits + QR)',
        'cta': 'Call-to-Action Slide (invite to interact)'
    }
    
    def __init__(self, config_path: str = "vitrine_config.json"):
        self.config_path = Path(config_path)
        self.static_dir = self.config_path.parent / "static" / "slides"
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Load existing config or create default"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"{Colors.YELLOW}Warning: Invalid JSON, creating new config{Colors.END}")
        
        return {
            "version": "2.0",
            "language": "fr",
            "slides": [],
            "scroll_messages": {"fr": [], "en": []},
            "settings": {
                "scroll_speed": 80,
                "auto_advance": True,
                "show_progress": True,
                "transition": "fade"
            },
            "branding": {
                "primary_color": "#00ff88",
                "secondary_color": "#00d4ff",
                "accent_color": "#ffd700"
            }
        }
    
    def save_config(self):
        """Save config to file"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
        print(f"{Colors.GREEN}✓ Config saved to {self.config_path}{Colors.END}")
    
    def ensure_static_dir(self):
        """Create static/slides directory if needed"""
        self.static_dir.mkdir(parents=True, exist_ok=True)
    
    def list_slides(self):
        """Display current slides"""
        slides = self.config.get('slides', [])
        if not slides:
            print(f"{Colors.YELLOW}No slides configured yet.{Colors.END}")
            return
        
        print(f"\n{Colors.CYAN}Current Slides ({len(slides)}):{Colors.END}")
        print("-" * 50)
        for i, slide in enumerate(slides, 1):
            stype = slide.get('type', 'unknown')
            title = slide.get('title', 'Untitled')
            duration = slide.get('duration', 10)
            highlight = " ⭐" if slide.get('highlight') else ""
            print(f"  {Colors.YELLOW}{i:2}.{Colors.END} [{stype:6}] {title} ({duration}s){highlight}")
        print("-" * 50)
    
    def create_title_slide(self) -> Dict[str, Any]:
        """Create a title slide"""
        print_header("Create Title Slide")
        return {
            "id": "",
            "type": "title",
            "title": get_input("Main title (with emoji)"),
            "subtitle": get_input("Subtitle", required=False),
            "background": "gradient",
            "duration": get_number("Duration (seconds)", 8)
        }
    
    def create_text_slide(self) -> Dict[str, Any]:
        """Create a text slide"""
        print_header("Create Text Slide")
        return {
            "id": "",
            "type": "text",
            "title": get_input("Title (with emoji)"),
            "content": get_input("Main content text"),
            "icon": get_input("Icon emoji", "💡", required=False),
            "duration": get_number("Duration (seconds)", 10)
        }
    
    def create_image_slide(self) -> Dict[str, Any]:
        """Create an image slide"""
        print_header("Create Image Slide")
        self.ensure_static_dir()
        
        title = get_input("Title (with emoji)")
        content = get_input("Caption/description", required=False)
        
        # Ask for image source
        print(f"\n{Colors.CYAN}Image source:{Colors.END}")
        print("  1. Copy from local file")
        print("  2. Use URL")
        print("  3. Use existing file in static/slides/")
        
        img_choice = get_choice(3)
        media_url = ""
        
        if img_choice == 1:
            src_path = get_input("Path to image file")
            if os.path.exists(src_path):
                filename = os.path.basename(src_path)
                dest = self.static_dir / filename
                shutil.copy2(src_path, dest)
                media_url = f"/static/slides/{filename}"
                print(f"{Colors.GREEN}✓ Image copied to {dest}{Colors.END}")
            else:
                print(f"{Colors.RED}File not found, using path as-is{Colors.END}")
                media_url = src_path
        elif img_choice == 2:
            media_url = get_input("Image URL")
        elif img_choice == 3:
            # List existing files
            existing = list(self.static_dir.glob("*.*")) if self.static_dir.exists() else []
            if existing:
                print(f"\n{Colors.CYAN}Existing files:{Colors.END}")
                for f in existing:
                    print(f"  - {f.name}")
            filename = get_input("Filename")
            media_url = f"/static/slides/{filename}"
        
        return {
            "id": "",
            "type": "image",
            "title": title,
            "content": content,
            "media_url": media_url,
            "media_alt": content or title,
            "duration": get_number("Duration (seconds)", 10)
        }
    
    def create_video_slide(self) -> Dict[str, Any]:
        """Create a video slide"""
        print_header("Create Video Slide")
        self.ensure_static_dir()
        
        title = get_input("Title (with emoji)")
        
        # Ask for video source
        print(f"\n{Colors.CYAN}Video source:{Colors.END}")
        print("  1. Copy from local file")
        print("  2. Use URL (IPFS, HTTP...)")
        print("  3. Use existing file in static/slides/")
        
        vid_choice = get_choice(3)
        media_url = ""
        
        if vid_choice == 1:
            src_path = get_input("Path to video file")
            if os.path.exists(src_path):
                filename = os.path.basename(src_path)
                dest = self.static_dir / filename
                shutil.copy2(src_path, dest)
                media_url = f"/static/slides/{filename}"
                print(f"{Colors.GREEN}✓ Video copied to {dest}{Colors.END}")
            else:
                media_url = src_path
        elif vid_choice == 2:
            media_url = get_input("Video URL")
        elif vid_choice == 3:
            existing = list(self.static_dir.glob("*.mp4")) + list(self.static_dir.glob("*.webm"))
            if existing:
                print(f"\n{Colors.CYAN}Existing videos:{Colors.END}")
                for f in existing:
                    print(f"  - {f.name}")
            filename = get_input("Filename")
            media_url = f"/static/slides/{filename}"
        
        return {
            "id": "",
            "type": "video",
            "title": title,
            "media_url": media_url,
            "media_poster": get_input("Poster image URL", "", required=False),
            "autoplay": get_yes_no("Autoplay?", True),
            "loop": get_yes_no("Loop?", False),
            "duration": get_number("Max duration (seconds)", 30, max_val=600)
        }
    
    def create_offer_slide(self) -> Dict[str, Any]:
        """Create an offer/pricing slide"""
        print_header("Create Offer Slide")
        
        title = get_input("Offer title (e.g., '💰 PALIER SOUTIEN')")
        price = get_input("Price (e.g., '50€')")
        
        print(f"\n{Colors.CYAN}Enter benefits (one per line, empty line to finish):{Colors.END}")
        benefits = []
        while True:
            benefit = input(f"  {len(benefits)+1}. ").strip()
            if not benefit:
                break
            benefits.append(benefit)
        
        return {
            "id": "",
            "type": "offer",
            "title": title,
            "price": price,
            "benefits": benefits,
            "cta": get_input("Call-to-action text", "Scannez pour rejoindre"),
            "qr_content": get_input("QR Code URL"),
            "highlight": get_yes_no("Highlight this offer?", False),
            "duration": get_number("Duration (seconds)", 12)
        }
    
    def create_cta_slide(self) -> Dict[str, Any]:
        """Create a call-to-action slide"""
        print_header("Create CTA Slide")
        return {
            "id": "",
            "type": "cta",
            "title": get_input("Title", "👋 Interagissez !"),
            "content": get_input("Instruction text", "Levez la main pour explorer"),
            "background": "animated",
            "duration": get_number("Duration (seconds)", 8)
        }
    
    def add_slide(self):
        """Add a new slide"""
        print_header("Add New Slide")
        
        types = list(self.SLIDE_TYPES.keys())
        print_menu([self.SLIDE_TYPES[t] for t in types], "Select slide type:")
        
        choice = get_choice(len(types))
        if choice == 0:
            return
        
        slide_type = types[choice - 1]
        
        # Create slide based on type
        creators = {
            'title': self.create_title_slide,
            'text': self.create_text_slide,
            'image': self.create_image_slide,
            'video': self.create_video_slide,
            'offer': self.create_offer_slide,
            'cta': self.create_cta_slide
        }
        
        slide = creators[slide_type]()
        slide['id'] = generate_id(slide.get('title', slide_type))
        
        # Add to config
        if 'slides' not in self.config:
            self.config['slides'] = []
        self.config['slides'].append(slide)
        
        print(f"\n{Colors.GREEN}✓ Slide '{slide['title']}' added!{Colors.END}")
        
        if get_yes_no("Add another slide?", True):
            self.add_slide()
    
    def edit_slide(self):
        """Edit an existing slide"""
        slides = self.config.get('slides', [])
        if not slides:
            print(f"{Colors.YELLOW}No slides to edit.{Colors.END}")
            return
        
        self.list_slides()
        idx = get_number("Slide number to edit", 1, 1, len(slides)) - 1
        slide = slides[idx]
        
        print(f"\n{Colors.CYAN}Editing: {slide.get('title')}{Colors.END}")
        print_menu([
            "Edit title",
            "Edit duration",
            "Edit content/details",
            "Toggle highlight",
            "Delete this slide"
        ])
        
        choice = get_choice(5)
        if choice == 1:
            slide['title'] = get_input("New title", slide.get('title', ''))
        elif choice == 2:
            slide['duration'] = get_number("New duration", slide.get('duration', 10))
        elif choice == 3:
            if 'content' in slide:
                slide['content'] = get_input("New content", slide.get('content', ''))
            if 'subtitle' in slide:
                slide['subtitle'] = get_input("New subtitle", slide.get('subtitle', ''))
        elif choice == 4:
            slide['highlight'] = not slide.get('highlight', False)
            print(f"Highlight: {'ON' if slide['highlight'] else 'OFF'}")
        elif choice == 5:
            if get_yes_no("Really delete this slide?", False):
                slides.pop(idx)
                print(f"{Colors.GREEN}✓ Slide deleted{Colors.END}")
    
    def reorder_slides(self):
        """Reorder slides"""
        slides = self.config.get('slides', [])
        if len(slides) < 2:
            print(f"{Colors.YELLOW}Need at least 2 slides to reorder.{Colors.END}")
            return
        
        self.list_slides()
        
        src = get_number("Move slide number", 1, 1, len(slides)) - 1
        dst = get_number("To position", 1, 1, len(slides)) - 1
        
        slide = slides.pop(src)
        slides.insert(dst, slide)
        
        print(f"{Colors.GREEN}✓ Slide moved{Colors.END}")
        self.list_slides()
    
    def edit_scroll_messages(self):
        """Edit scroll messages"""
        print_header("Edit Scroll Messages")
        
        lang = get_input("Language code", "fr")
        if 'scroll_messages' not in self.config:
            self.config['scroll_messages'] = {}
        
        current = self.config['scroll_messages'].get(lang, [])
        if current:
            print(f"\n{Colors.CYAN}Current messages:{Colors.END}")
            for i, msg in enumerate(current, 1):
                print(f"  {i}. {msg}")
        
        print(f"\n{Colors.CYAN}Enter new messages (one per line, empty to finish):{Colors.END}")
        messages = []
        while True:
            msg = input(f"  {len(messages)+1}. ").strip()
            if not msg:
                break
            messages.append(msg)
        
        if messages:
            self.config['scroll_messages'][lang] = messages
            print(f"{Colors.GREEN}✓ {len(messages)} messages saved for '{lang}'{Colors.END}")
    
    def edit_branding(self):
        """Edit branding settings"""
        print_header("Edit Branding")
        
        branding = self.config.get('branding', {})
        
        branding['primary_color'] = get_input("Primary color (hex)", branding.get('primary_color', '#00ff88'))
        branding['secondary_color'] = get_input("Secondary color (hex)", branding.get('secondary_color', '#00d4ff'))
        branding['accent_color'] = get_input("Accent color (hex)", branding.get('accent_color', '#ffd700'))
        branding['logo_url'] = get_input("Logo URL", branding.get('logo_url', ''), required=False)
        branding['ico_url'] = get_input("ICO/Main URL", branding.get('ico_url', ''), required=False)
        
        self.config['branding'] = branding
        print(f"{Colors.GREEN}✓ Branding updated{Colors.END}")
    
    def preview_config(self):
        """Show config summary"""
        print_header("Configuration Summary")
        
        slides = self.config.get('slides', [])
        total_duration = sum(s.get('duration', 10) for s in slides)
        
        print(f"{Colors.CYAN}Version:{Colors.END} {self.config.get('version', '1.0')}")
        print(f"{Colors.CYAN}Language:{Colors.END} {self.config.get('language', 'fr')}")
        print(f"{Colors.CYAN}Slides:{Colors.END} {len(slides)}")
        print(f"{Colors.CYAN}Total duration:{Colors.END} {total_duration}s ({total_duration//60}m {total_duration%60}s)")
        
        self.list_slides()
        
        scroll = self.config.get('scroll_messages', {})
        for lang, msgs in scroll.items():
            print(f"\n{Colors.CYAN}Scroll messages ({lang}):{Colors.END} {len(msgs)} messages")
    
    def run(self):
        """Main CLI loop"""
        print_header("🎬 Vitrine Slideshow Builder")
        print(f"Config file: {self.config_path}")
        
        while True:
            print_menu([
                "📋 List slides",
                "➕ Add new slide",
                "✏️  Edit slide",
                "🔀 Reorder slides",
                "📝 Edit scroll messages",
                "🎨 Edit branding",
                "👁️  Preview config",
                "💾 Save & Exit",
                "🚪 Exit without saving"
            ], "\nMain Menu:")
            
            choice = get_choice(9)
            
            if choice == 0 or choice == 9:
                if get_yes_no("Exit without saving?", False):
                    print(f"{Colors.YELLOW}Bye!{Colors.END}")
                    break
            elif choice == 1:
                self.list_slides()
            elif choice == 2:
                self.add_slide()
            elif choice == 3:
                self.edit_slide()
            elif choice == 4:
                self.reorder_slides()
            elif choice == 5:
                self.edit_scroll_messages()
            elif choice == 6:
                self.edit_branding()
            elif choice == 7:
                self.preview_config()
            elif choice == 8:
                self.save_config()
                print(f"{Colors.GREEN}✓ Configuration saved. Bye!{Colors.END}")
                break


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Interactive slideshow builder for Vitrine Interactive",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 slideshow_builder.py                    # Use default config
  python3 slideshow_builder.py -c my_config.json  # Use custom config
  python3 slideshow_builder.py --list             # Just list slides
        """
    )
    parser.add_argument('-c', '--config', default='vitrine_config.json',
                        help='Path to config file (default: vitrine_config.json)')
    parser.add_argument('--list', action='store_true',
                        help='Just list current slides and exit')
    
    args = parser.parse_args()
    
    builder = SlideBuilder(args.config)
    
    if args.list:
        builder.list_slides()
        return
    
    try:
        builder.run()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Interrupted. Bye!{Colors.END}")
        sys.exit(0)


if __name__ == "__main__":
    main()


