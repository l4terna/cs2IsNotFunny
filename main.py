from fastapi import FastAPI, Request
import edge_tts
import pygame
import asyncio
import httpx
import uvicorn
import os, sys
import winreg
import shutil



app = FastAPI()

prevHealth = None

@app.post("/cs2")
async def cs2_gsi(req: Request):
    global prevHealth

    data = await req.json()
    
    print(data)

    if data["auth"]["key1"] != "bigballskidsyettys": 
        return {"ok": True}
    
    currentHealth = data["player"]["state"]["health"]

    if currentHealth != prevHealth or prevHealth is None:
        prevHealth = currentHealth

        if currentHealth == 0:
            asyncio.create_task(play_zen_quote_and_music())


    return {"ok": True}


async def play_zen_quote_and_music():
    async with httpx.AsyncClient(timeout=10) as client:
        quoteRes = await client.get(
            "http://api.forismatic.com/api/1.0/",
            params={"method": "getQuote", "format": "json", "lang": "ru"},
        )
    quoteData = quoteRes.json()

    communicate = edge_tts.Communicate(f"{quoteData["quoteText"]}. {quoteData["quoteAuthor"]}", voice="ru-RU-DmitryNeural", rate="-25%", pitch="-8Hz")
    await communicate.save("quote.mp3")

    pygame.mixer.init()
    pygame.mixer.music.load(resource_path("zen.mp3"))
    pygame.mixer.music.set_volume(0.15)
    pygame.mixer.music.play()
    
    voice = pygame.mixer.Sound("quote.mp3")
    channel = voice.play()

    while channel.get_busy():
        await asyncio.sleep(0.1)

    pygame.mixer.music.fadeout(2000)


def resource_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(sys.argv[0]))
    return os.path.join(base, rel)


def find_cs2_cfg_path() -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            steamPath, _ = winreg.QueryValueEx(k, "SteamPath")
    except FileNotFoundError:
        return None

    steamPath = steamPath.replace("/", "\\")
    libraries = [steamPath]

    for lib in libraries:
        csPath = os.path.join(lib, "steamapps", "common", "Counter-Strike Global Offensive")
        cfgPath = os.path.join(csPath, "game", "csgo", "cfg")
        if os.path.isdir(cfgPath):
            return cfgPath

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