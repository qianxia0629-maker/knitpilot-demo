"""Stage the shared Python API and static Next.js export for Cloudflare Workers."""

from pathlib import Path
from shutil import copy2, copytree, rmtree


def prepare(root: Path) -> tuple[int, int]:
    """Copy source and assets only; never bundle virtualenvs or generated caches."""
    export = root / "apps/web/out"
    required = ("index.html", "demo-spec.json", "_next")
    missing = [name for name in required if not (export / name).exists()]
    if missing:
        raise ValueError(f"Run npm --prefix apps/web run build first; missing: {', '.join(missing)}")

    deployment = root / "deploy/cloudflare"
    source = deployment / "src"
    count = 0
    # These generated copies are ignored by git. The original shared code is authoritative.
    for package in ("apps", "packages"):
        target = source / package
        if target.exists():
            rmtree(target)
        target.mkdir(parents=True)
        copy2(root / package / "__init__.py", target / "__init__.py")
        count += 1
    for package in ("apps/api", "packages/schemas", "packages/engine"):
        for original in sorted((root / package).rglob("*.py")):
            if "__pycache__" in original.parts:
                continue
            target = source / original.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            copy2(original, target)
            count += 1

    public = deployment / "public"
    if public.exists():
        rmtree(public)
    public.mkdir(parents=True)
    copytree(export, public / "demo")
    assets = sum(1 for file in public.rglob("*") if file.is_file())
    return count, assets


if __name__ == "__main__":
    files, assets = prepare(Path(__file__).resolve().parents[1])
    print(f"Cloudflare bundle prepared: {files} Python files, {assets} static assets.")
