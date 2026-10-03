import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent

INACTIVE = (
    'rounded-full px-5 py-1.5 text-xs font-bold border-[1.5px] border-slate-900 '
    'bg-white text-slate-800 hover:bg-slate-100 transition inline-flex items-center '
    'justify-center shrink-0'
)
ACTIVE = (
    'rounded-full px-5 py-1.5 text-xs font-bold border-2 border-slate-950 bg-[#F0E6FF] '
    'text-[#3B1262] shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] inline-flex items-center '
    'justify-center shrink-0'
)
TABS = [
    ("/social", "LinkedIn &amp; X"),
    ("/video", "Video Script &amp; Preview"),
    ("/advisory", "Official Advisory"),
    ("/summary", "Executive Summary"),
    ("/slides", "Slide Deck"),
    ("/infographics", "Infographics"),
]
ICON_LINK = (
    '<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:'
    'opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet"/>'
)


def build_header(active_href: str) -> str:
    items = []
    for href, label in TABS:
        if href == active_href:
            items.append(
                f'<a href="{href}" class="{ACTIVE}" aria-current="page">{label}</a>'
            )
        else:
            items.append(f'<a href="{href}" class="{INACTIVE}">{label}</a>')
    tabs = "".join(items)
    return f'''<header class="sticky top-0 left-0 right-0 z-50 bg-white border-b-[1.5px] border-slate-900">
  <div class="h-16 max-w-[1280px] mx-auto px-6 grid grid-cols-[1fr_auto_1fr] items-center gap-4">
    <span class="justify-self-start font-extrabold tracking-tight text-slate-950 shrink-0" style="font-family: 'Plus Jakarta Sans', 'Inter', system-ui, sans-serif; font-weight: 800; font-size: 1.5rem; letter-spacing: -0.02em;">UnifiOps</span>
    <div class="hidden sm:flex items-center justify-center gap-2 min-w-0">
      <div class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border-[1.5px] border-slate-900 bg-white font-bold uppercase text-[10px] tracking-wide text-slate-800">
        <span class="material-symbols-outlined text-[15px] leading-none shrink-0">description</span>
        <span id="sourceDocumentBadge" class="truncate max-w-[200px] leading-none">Uploaded Document</span>
      </div>
      <span id="audienceBadge" class="inline-flex items-center justify-center px-3 py-1 rounded-full border-[1.5px] border-slate-900 bg-[#C8F250] text-slate-900 font-bold uppercase text-[10px] tracking-wide leading-none shrink-0">General</span>
      <span id="toneBadge" class="inline-flex items-center justify-center px-3 py-1 rounded-full border-[1.5px] border-slate-900 bg-[#E1E0FF] text-slate-800 font-bold uppercase text-[10px] tracking-wide leading-none shrink-0">Professional</span>
    </div>
    <div class="justify-self-end flex items-center gap-3 shrink-0">
      <a class="inline-flex items-center px-4 py-1.5 bg-white text-slate-900 border-[1.5px] border-slate-900 rounded-full text-xs font-bold shadow-[3px_3px_0px_#1c1b20] hover:translate-x-[-1px] hover:translate-y-[-1px] hover:shadow-[4px_4px_0px_#1c1b20] transition-all" data-path="deliverables-list" href="/processing">← Back to All Deliverables</a>
      <div class="w-8 h-8 rounded-full bg-slate-950 flex items-center justify-center border-[1.5px] border-slate-900 shadow-[2px_2px_0px_#1c1b20]"><span class="material-symbols-outlined text-white text-[18px]">person</span></div>
    </div>
  </div>
  <div class="h-14 border-t-[1.5px] border-slate-900 bg-white flex items-center">
    <nav class="max-w-[1280px] mx-auto px-6 w-full flex flex-row flex-nowrap items-center justify-center gap-2.5 overflow-x-auto no-scrollbar py-1" role="navigation" aria-label="Deliverable navigation">{tabs}</nav>
  </div>
</header>'''


TARGETS = {
    "02_social.html": "/social",
    "04_social_media.html": "/social",
    "03_video.html": "/video",
    "05_video.html": "/video",
    "06_summary.html": "/summary",
    "07_infographics.html": "/infographics",
    "08_advisory.html": "/advisory",
    "09_slides.html": "/slides",
}


def replace_header(text: str, header: str) -> str:
    new, n = re.subn(r"<header\b[\s\S]*?</header>", header, text, count=1)
    if n != 1:
        raise RuntimeError("Could not replace exactly one header")
    return new


def ensure_icons(text: str) -> str:
    if "Material+Symbols+Outlined" in text:
        return text
    return text.replace("</head>", ICON_LINK + "\n</head>", 1)


def strip_infographic_inline_tabs(text: str) -> str:
    text = re.sub(
        r"<!-- 6 Horizontal Clean Pill Tabs \(Single Line, 12px Gaps\) -->\s*",
        "",
        text,
        count=1,
    )
    text = re.sub(
        r'<div class="flex flex-row flex-nowrap items-center gap-2\.5 my-4 w-full overflow-x-auto no-scrollbar py-1" role="navigation" aria-label="Deliverable navigation">[\s\S]*?</div>',
        "",
        text,
        count=1,
    )
    return text


def main():
    for name, active in TARGETS.items():
        path = ROOT / name
        text = path.read_text(encoding="utf-8")
        text = ensure_icons(text)
        text = replace_header(text, build_header(active))
        if name == "07_infographics.html":
            text = strip_infographic_inline_tabs(text)
            text = text.replace(
                '<main class="w-full pt-16 bg-surface-container-lowest min-h-[calc(100vh-53px)]">',
                '<main class="w-full pt-4 bg-surface-container-lowest min-h-[calc(100vh-53px)]">',
                1,
            )
        if "Next:" in text.split("</header>", 1)[0]:
            raise RuntimeError(f"{name} still has Next in header")
        path.write_text(text, encoding="utf-8")
        print("updated", name)


if __name__ == "__main__":
    main()
