from __future__ import annotations

from pathlib import Path


class SSKRenderError(RuntimeError):
    pass


def render_pdf_with_ssk(
    *,
    xml_path: Path,
    pdf_path: Path,
    app_url: str = "https://www.elohnausweis-ssk.ch/",
    timeout_ms: int = 240_000,
    headless: bool = True,
) -> None:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SSKRenderError(
            "Playwright is required for SSK PDF rendering. Install it with "
            "`python -m pip install playwright` and `python -m playwright install chromium`."
        ) from exc

    xml_path = xml_path.resolve()
    pdf_path = pdf_path.resolve()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        try:
            context = browser.new_context(locale="de-CH", accept_downloads=True)
            page = context.new_page()
            page.goto(app_url, wait_until="networkidle", timeout=60_000)

            page.get_by_role("button", name="LOHNAUSWEISE ÖFFNEN").click(timeout=30_000)
            page.locator("input[type=file]").set_input_files(str(xml_path))
            page.get_by_role("button", name="WEITER").click(timeout=30_000)
            page.wait_for_url("**/arbeitnehmer", timeout=30_000)

            page.locator("button").filter(has_text="alle LA").click(timeout=30_000)
            if page.get_by_role("button", name="Überspringen").is_visible(timeout=5_000):
                page.get_by_role("button", name="Überspringen").click(timeout=30_000)

            with page.expect_download(timeout=timeout_ms) as download_info:
                page.get_by_role("button", name="Alle in einem PDF").click(timeout=30_000)
            download = download_info.value
            download.save_as(str(pdf_path))
        except PlaywrightTimeoutError as exc:
            raise SSKRenderError("Timed out while rendering PDF through the SSK web app.") from exc
        finally:
            browser.close()
