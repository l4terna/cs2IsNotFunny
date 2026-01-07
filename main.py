from fastapi import FastAPI, Request
import edge_tts
import pygame
import asyncio
import httpx
import uvicorn
import os, sys
import winreg
import shutil
import random
import re
from typing import Optional, List

app = FastAPI()

prevHealth = None
voiceChannel = None
voice_lock = asyncio.Lock()


MUSIC_VOL = 0.25
MUSIC_DUCK = 0.2
VOICE_VOL = 0.6

pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
pygame.mixer.set_num_channels(8)

VOICE_CH = pygame.mixer.Channel(0) 


@app.post("/cs2")
async def cs2_gsi(req: Request):
    global prevHealth

    data = await req.json()
    
    print(data)

    if data.get("auth", {}).get("key1") != "bigballskidsyettys":
        return {"ok": True}
    
    currentHealth = data.get("player", {}).get("state", {}).get("health")

    if currentHealth is None:
        return {"ok": True}
    
    providerSteamid = data.get("provider", {}).get("steamid", {})
    playerSteamid = data.get("player", {}).get("steamid", {})

    if providerSteamid == playerSteamid and currentHealth != prevHealth or prevHealth is None:
        prevHealth = currentHealth

        if currentHealth == 0:
            asyncio.create_task(play_zen_quote_and_music())


    return {"ok": True}


async def safe_remove(path: str):
    for _ in range(10):
        try:
            os.remove(path)
            return
        except PermissionError:
            await asyncio.sleep(0.1)
        except FileNotFoundError:
            return

async def play_zen_quote_and_music():
    if voice_lock.locked():
        return

    async with voice_lock:
        async with httpx.AsyncClient(timeout=10) as client:
            quoteRes = await client.get(
                "http://api.forismatic.com/api/1.0/",
                params={"method": "getQuote", "format": "json", "lang": "ru"},
            )
        quoteData = quoteRes.json()
        
        text = f'{quoteData.get("quoteText","")}. {quoteData.get("quoteAuthor","")}'.strip()

        communicate = edge_tts.Communicate(
            text,
            voice="ru-RU-DmitryNeural",
            rate="-25%",
            pitch="-8Hz",
        )
        await communicate.save("quote.mp3")

        zenNumber = random.randint(1, 3)
        pygame.mixer.music.load(resource_path(f"music/zen{zenNumber}.mp3"))
        pygame.mixer.music.set_volume(MUSIC_VOL)
        pygame.mixer.music.play(-1) 

        pygame.mixer.music.set_volume(MUSIC_DUCK)

        voice = pygame.mixer.Sound("quote.mp3")
        VOICE_CH.set_volume(VOICE_VOL)
        VOICE_CH.play(voice)

        while VOICE_CH.get_busy():
            await asyncio.sleep(0.05)

        pygame.mixer.music.set_volume(MUSIC_VOL)
        pygame.mixer.music.fadeout(1500)

        del voice
        await asyncio.sleep(0.15)
        await safe_remove("quote.mp3")


def resource_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.argv[0])))
    rel = rel.lstrip("/\\")
    return os.path.normpath(os.path.join(base, rel))

def get_steam_path() -> Optional[str]:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            steamPath, _ = winreg.QueryValueEx(k, "SteamPath")
            steamPath = steamPath.replace("/", "\\")
            return steamPath
    except FileNotFoundError:
        return None

def read_steam_libraries(steam_path: str) -> List[str]:
    libs = []
    if steam_path:
        libs.append(os.path.normpath(steam_path))

    vdf_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
    if not os.path.isfile(vdf_path):
        return list(dict.fromkeys(libs))

    try:
        raw = open(vdf_path, "r", encoding="utf-8", errors="ignore").read()
    except OSError:
        return list(dict.fromkeys(libs))

    paths = set()

    for m in re.finditer(r'"\s*path\s*"\s*"([^"]+)"', raw, flags=re.IGNORECASE):
        p = m.group(1).replace("/", "\\")
        paths.add(os.path.normpath(p))

    for m in re.finditer(r'"\s*\d+\s*"\s*"([^"]+)"', raw):
        p = m.group(1).replace("/", "\\")
        p = os.path.normpath(p)

        if os.path.isdir(os.path.join(p, "steamapps")):
            paths.add(p)

    for p in sorted(paths):
        libs.append(p)

    libs = list(dict.fromkeys(libs))
    return libs

def find_cs2_cfg_path() -> Optional[str]:
    steam_path = get_steam_path()
    if not steam_path:
        return None

    libraries = read_steam_libraries(steam_path)

    common_rel = os.path.join("steamapps", "common")
    candidates = [
        "Counter-Strike Global Offensive", 
        "Counter-Strike 2",                
    ]

    for lib in libraries:
        common_dir = os.path.join(lib, common_rel)
        for folder in candidates:
            cs_root = os.path.join(common_dir, folder)
            cfg_path = os.path.join(cs_root, "game", "csgo", "cfg")
            if os.path.isdir(cfg_path):
                return cfg_path

    return None

def insert_cfg():
    cfgPath = find_cs2_cfg_path()

    if cfgPath is None:
        print("ПУТЬ ДО ПАПКИ С КОНФИГУРАЦИОННЫМИ ФАЙЛАМИ НЕ НАЙДЕН. НЕОБХОДИМА РУЧНАЯ ВСТАВКА")
        return
    
    cfgFilePath = cfgPath + "/gamestate_integration_laterna.cfg"
    
    if not os.path.exists(cfgFilePath):
        shutil.copy(resource_path("gamestate_integration_laterna.cfg"), cfgFilePath)
    


if __name__ == "__main__":
    insert_cfg()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )