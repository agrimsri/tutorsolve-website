"""
Advanced Preview Generation Service (Module 8 - Enhanced)
Handles PDF, Code/Text, and Images with strict security and obfuscation rules.
"""
import io
import os
import math
import logging
from PIL import Image, ImageFilter, ImageDraw, ImageFont

# Configure logging
logger = logging.getLogger(__name__)

def generate_preview(file_path: str):
    """
    Main entry point for preview generation.
    Routes to specialized handlers based on extension.
    """
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return {"preview_available": False, "message": "Source file not found"}

    ext = os.path.splitext(file_path)[1].lower().strip(".")
    
    try:
        if ext == "pdf":
            return handle_pdf(file_path)
        elif ext in ("py", "js", "java", "cpp", "c", "cs", "txt"):
            return handle_text(file_path)
        elif ext in ("png", "jpg", "jpeg"):
            return handle_image(file_path)
        else:
            return {
                "preview_available": False,
                "message": f"Preview not available for .{ext} files"
            }
    except Exception as e:
        logger.error(f"Error generating preview for {file_path}: {str(e)}")
        return {"preview_available": False, "message": "An error occurred during preview generation"}

def handle_pdf(file_path: str):
    try:
        import PyPDF2
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()
            
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        
        # Check if encrypted
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except:
                return {"preview_available": False, "message": "Encrypted PDF: Preview not available"}

        total_pages = len(reader.pages)
        if total_pages == 0:
            return {"preview_available": False, "message": "Empty PDF"}

        # For short PDFs (1-2 pages), a watermark-only preview leaks all content.
        # Instead, render to image and apply blur like the image handler.
        if total_pages <= 2:
            return _handle_pdf_as_blurred_image(file_path, pdf_bytes, reader)

        # Calculate preview pages: max(1, min(3, floor(0.25 * total_pages)))
        preview_count = max(1, min(3, math.floor(0.25 * total_pages)))

        # Limit processing for very large PDFs
        preview_count = min(preview_count, 20)

        writer = PyPDF2.PdfWriter()
        
        # Create a watermark PDF page
        watermark_bytes = create_pdf_watermark_page()
        wm_reader = PyPDF2.PdfReader(io.BytesIO(watermark_bytes))
        wm_page = wm_reader.pages[0]

        for i in range(preview_count):
            page = reader.pages[i]
            # Merge watermark
            try:
                page.merge_page(wm_page)
            except:
                pass # Continue without watermark if merge fails
            writer.add_page(page)

        # Save to temp file
        preview_path = file_path + ".preview.pdf"
        with open(preview_path, "wb") as f:
            writer.write(f)
            
        return preview_path
    except Exception as e:
        logger.error(f"PDF Handler Error: {str(e)}")
        return {"preview_available": False, "message": "Failed to process PDF preview"}


def _handle_pdf_as_blurred_image(file_path: str, pdf_bytes: bytes, reader):
    """
    For short PDFs (1-2 pages), render the first page to an image and apply
    the same blur + watermark treatment used for image previews.
    This prevents single-page PDFs from leaking full content.
    """
    try:
        # Try PyMuPDF (fitz) first for high-quality rendering
        try:
            import fitz
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            page = doc[0]
            # Render at 150 DPI for good quality
            pix = page.get_pixmap(dpi=150)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            doc.close()
        except ImportError:
            # Fallback: Create a placeholder image with extracted text
            logger.info("[Preview] PyMuPDF not available, using text-extraction fallback for short PDF")
            page = reader.pages[0]
            
            # Get page dimensions (in points, 72 dpi)
            media_box = page.mediabox
            page_w = int(float(media_box.width))
            page_h = int(float(media_box.height))
            # Scale up for readability
            scale = 2
            w, h = page_w * scale, page_h * scale
            
            # Extract text content
            text = page.extract_text() or ""
            
            # Create image with text rendered on it
            img = Image.new("RGB", (w, h), (255, 255, 255))
            draw = ImageDraw.Draw(img)
            
            font = get_system_font(14 * scale)
            
            # Wrap and draw text
            margin = 40 * scale
            y = margin
            for line in text.split("\n"):
                if y > h - margin:
                    break
                draw.text((margin, y), line[:120], fill=(30, 30, 30), font=font)
                y += 18 * scale
        
        # Now apply blur + watermark (same logic as handle_image)
        w, h = img.size
        img = img.convert("RGBA")
        
        if w < 100 or h < 100:
            result = img.filter(ImageFilter.GaussianBlur(radius=20))
        else:
            # Blur central region (middle 50%)
            top_h = h // 4
            bottom_h = h // 4
            middle_h = h - top_h - bottom_h
            
            middle_box = (0, top_h, w, top_h + middle_h)
            middle_region = img.crop(middle_box).filter(ImageFilter.GaussianBlur(radius=20))
            
            result = img.copy()
            result.paste(middle_region, (0, top_h))
        
        # Add Watermark
        watermark_layer = Image.new('RGBA', (w, h), (255, 255, 255, 0))
        draw = ImageDraw.Draw(watermark_layer)
        
        fsize = max(20, min(w, h) // 8)
        font = get_system_font(fsize)
        
        text = "PREVIEW"
        tw, th = draw.textbbox((0, 0), text, font=font)[2:]
        draw.text(((w - tw) // 2, (h - th) // 2), text, fill=(180, 180, 180, 140), font=font)
        
        watermark_layer = watermark_layer.rotate(30, expand=False, resample=Image.BICUBIC)
        
        combined = Image.alpha_composite(result, watermark_layer)
        final = combined.convert("RGB")
        
        preview_path = file_path + ".preview.jpg"
        final.save(preview_path, format="JPEG", quality=85)
        
        return preview_path
    except Exception as e:
        logger.error(f"PDF-as-image Handler Error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {"preview_available": False, "message": "Failed to process short PDF preview"}

def create_pdf_watermark_page():
    """Generates a PDF page with 'PREVIEW' text using Pillow"""
    # A4 size at 72dpi is 595x842
    w, h = 595, 842
    img = Image.new('RGBA', (w, h), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    font = get_system_font(80)
    
    # Draw PREVIEW diagonally
    text = "PREVIEW"
    # Create a separate layer for rotated text
    txt_layer = Image.new('RGBA', (w, h), (255, 255, 255, 0))
    tdraw = ImageDraw.Draw(txt_layer)
    
    # Calculate center
    tw, th = tdraw.textbbox((0, 0), text, font=font)[2:]
    tdraw.text(((w - tw) // 2, (h - th) // 2), text, fill=(150, 150, 150, 100), font=font)
    
    # Rotate
    txt_layer = txt_layer.rotate(45, expand=False, resample=Image.BICUBIC)
    img.paste(txt_layer, (0, 0), txt_layer)
    
    pdf_io = io.BytesIO()
    img.save(pdf_io, format="PDF")
    return pdf_io.getvalue()

def handle_text(file_path: str):
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            
        total_lines = len(lines)
        if total_lines == 0:
            return {"preview_available": False, "message": "Empty file"}
            
        if total_lines == 1:
            content = "Preview not available for very small files (single line detected)."
        elif total_lines <= 5:
            preview_lines = lines[:min(3, total_lines // 2 + 1)]
            content = "".join(preview_lines) + "\n... [Remaining content hidden]"
        else:
            # Show first 15% and last 10%, mask middle
            first_count = max(1, int(0.15 * total_lines))
            last_count = max(1, int(0.10 * total_lines))
            
            if first_count + last_count >= total_lines:
                first_count = max(1, total_lines // 3)
                last_count = max(1, total_lines // 5)
            
            content = (
                "".join(lines[:first_count]) + 
                "\n\n... [SENSITIVE CONTENT OMITTED] ...\n\n" + 
                "".join(lines[-last_count:])
            )

        preview_path = file_path + ".preview.txt"
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        return preview_path
    except Exception as e:
        logger.error(f"Text Handler Error: {str(e)}")
        return {"preview_available": False, "message": "Failed to process text preview"}

def handle_image(file_path: str):
    try:
        img = Image.open(file_path).convert("RGBA")
        w, h = img.size
        
        # Safeguard for very small images
        if w < 100 or h < 100:
            result = img.filter(ImageFilter.GaussianBlur(radius=20))
        else:
            # Blur central region (middle 50%)
            top_h = h // 4
            bottom_h = h // 4
            middle_h = h - top_h - bottom_h
            
            middle_box = (0, top_h, w, top_h + middle_h)
            middle_region = img.crop(middle_box).filter(ImageFilter.GaussianBlur(radius=20))
            
            result = img.copy()
            result.paste(middle_region, (0, top_h))
            
        # Add Watermark
        watermark_layer = Image.new('RGBA', (w, h), (255, 255, 255, 0))
        draw = ImageDraw.Draw(watermark_layer)
        
        fsize = max(20, min(w, h) // 8)
        font = get_system_font(fsize)
        
        text = "PREVIEW"
        # Center watermark
        tw, th = draw.textbbox((0, 0), text, font=font)[2:]
        draw.text(((w - tw) // 2, (h - th) // 2), text, fill=(255, 255, 255, 120), font=font)
        
        # Rotate watermark
        watermark_layer = watermark_layer.rotate(30, expand=False, resample=Image.BICUBIC)
        
        # Final composition
        combined = Image.alpha_composite(result, watermark_layer)
        # Convert to RGB (JPEG doesn't support alpha)
        final = combined.convert("RGB")
        
        preview_path = file_path + ".preview.jpg"
        final.save(preview_path, format="JPEG", quality=85)
        
        return preview_path
    except Exception as e:
        logger.error(f"Image Handler Error: {str(e)}")
        return {"preview_available": False, "message": "Failed to process image preview"}

def get_system_font(size):
    """Attempts to load a standard system font, falls back to default"""
    font_paths = [
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-RI.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
    return ImageFont.load_default()
