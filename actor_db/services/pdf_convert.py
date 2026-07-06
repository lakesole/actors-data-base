import subprocess

DATA_DIR = "/volume2/damactors/전체 공유/actor_db/data"
LIBRE_CONTAINER = "libreoffice"

def convert_to_pdf(filename: str) -> str:
    cmd = [
        "sudo", "docker", "exec", LIBRE_CONTAINER,
        "soffice",
        "--headless",
        "--nologo",
        "--nofirststartwizard",
        "--convert-to", "pdf",
        "--outdir", "/data",
        f"/data/{filename}"
    ]

    subprocess.run(cmd, check=True)

    return filename.rsplit(".", 1)[0] + ".pdf"
