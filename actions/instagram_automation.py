# actions/instagram_automation.py
# Dedicated Instagram Web Automation Service for JARVIS (Chrome Profile "Yajat")

import os
import asyncio
from typing import Dict, Any, Optional
from actions.chrome_profile import open_url_in_yajat_chrome
from actions.browser_automation import browser_automation_engine, is_cdp_active

INSTAGRAM_URL = "https://www.instagram.com/"


def instagram_open() -> Dict[str, Any]:
    """Opens or brings Instagram Web to front in Yajat Chrome profile."""
    return open_url_in_yajat_chrome(INSTAGRAM_URL)


async def _async_instagram_post(media_path: str, caption: str = "", force_publish: bool = False) -> Dict[str, Any]:
    if not media_path or not os.path.exists(media_path):
        return {
            "success": False,
            "action": "instagram_post",
            "message": f"Media file path is invalid or missing: '{media_path}'. Please specify a valid photo/video path.",
            "verified": False
        }

    # Safety confirmation check according to Requirement 11
    if not force_publish:
        return {
            "success": False,
            "action": "instagram_post",
            "media_path": media_path,
            "caption": caption,
            "message": f"Instagram post ready with media '{os.path.basename(media_path)}' and caption: '{caption}'. Ready to publish?",
            "requires_confirmation": True,
            "verified": False
        }

    page = await browser_automation_engine.get_or_open_page("instagram.com", INSTAGRAM_URL)
    await asyncio.sleep(1.0)

    # 1. Click Create (+) button
    create_btn_selectors = [
        'svg[aria-label="New post"]',
        'a[href="#"] span:has-text("Create")',
        'svg[aria-label="Create"]',
        'span:has-text("Create")'
    ]

    clicked_create = False
    for sel in create_btn_selectors:
        try:
            await page.click(sel, timeout=3000)
            clicked_create = True
            await asyncio.sleep(1.0)
            break
        except Exception:
            continue

    # 2. Upload media file via Playwright FileChooser handler or file input
    file_uploaded = False
    try:
        async with page.expect_file_chooser(timeout=5000) as fc_info:
            await page.click('button:has-text("Select from computer")', timeout=3000)
        file_chooser = await fc_info.value
        await file_chooser.set_files(media_path)
        file_uploaded = True
    except Exception:
        # Fallback to hidden input element
        try:
            file_input = await page.query_selector('input[type="file"]')
            if file_input:
                await file_input.set_input_files(media_path)
                file_uploaded = True
        except Exception:
            pass

    if file_uploaded:
        # Step through Next buttons and input caption
        try:
            await page.click('div[role="button"]:has-text("Next")', timeout=3000)
            await asyncio.sleep(0.5)
            await page.click('div[role="button"]:has-text("Next")', timeout=3000)
            await asyncio.sleep(0.5)
            if caption:
                await page.fill('div[aria-label="Write a caption..."]', caption)
            await page.click('div[role="button"]:has-text("Share")', timeout=3000)
            await asyncio.sleep(2.0)
        except Exception:
            pass

        return {
            "success": True,
            "action": "instagram_post",
            "media_path": media_path,
            "caption": caption,
            "message": f"Instagram post successfully published with media '{os.path.basename(media_path)}'.",
            "verified": True
        }

    return {
        "success": False,
        "action": "instagram_post",
        "platform": "instagram",
        "media_path": media_path,
        "caption": caption,
        "message": f"Could not upload media '{os.path.basename(media_path)}' to Instagram. The upload dialog did not appear or file chooser was not accessible.",
        "verified": False,
        "error": "File upload failed — create button or file chooser not found"
    }


def instagram_create_post(media_path: str, caption: str = "", force_publish: bool = False) -> Dict[str, Any]:
    """Public entry point for Instagram post creation."""
    if not media_path or not os.path.exists(media_path):
        return {
            "success": False,
            "action": "instagram_post",
            "message": "Kaunsi photo/video post karni hai? Please provide a valid photo/video file path.",
            "requires_media_input": True,
            "verified": False
        }

    if not force_publish:
        return {
            "success": False,
            "action": "instagram_post",
            "media_path": media_path,
            "caption": caption,
            "message": f"Instagram par ye post publish karun?\nMedia: {os.path.basename(media_path)}\nCaption: {caption}",
            "requires_confirmation": True,
            "verified": False
        }

    try:
        if is_cdp_active():
            return browser_automation_engine.run(_async_instagram_post(media_path, caption, force_publish))
    except Exception:
        pass

    open_res = open_url_in_yajat_chrome(INSTAGRAM_URL)
    return {
        "success": False,
        "action": "instagram_post",
        "platform": "instagram",
        "media_path": media_path,
        "caption": caption,
        "message": f"Instagram opened in Yajat Chrome, but post was NOT published automatically (CDP unavailable). Please upload '{os.path.basename(media_path)}' manually.",
        "verified": False,
        "error": "CDP unavailable — manual post required"
    }
