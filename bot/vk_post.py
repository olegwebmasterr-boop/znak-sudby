#!/usr/bin/env python3
"""Вечерний пост в сообщество ВК «Знак судьбы» для GitHub Actions (аналог max_daily).
Контент — УНИКАЛЬНЫЙ, не копия МАКС/Дзена: очередь bot/vk_queue.json, пост = день месяца
по счётчику без состояния (len очередь >= 31 → каждый день новый; сейчас циклично).
Обложка: 1) bot/img/next_cover_vk_<дд.мм>.png (заготовка агента) 2) PIL из max_daily
3) без картинки (пост текстом — ВК допускает).
Режимы: print (локальная проверка текста+обложки), post (публикация; по умолчанию).
Свободный пост: env VK_CUSTOM_TEXT (через GitHub Actions «Run workflow», поле text)
или CLI-аргумент «post ТЕКСТ» — публикуется заданный текст вместо очереди; суффикс
сайта и обложка-карта дня добавляются автоматически.
VK API: photos.getWallUploadServer → upload → photos.saveWallPhoto → wall.post.
Токен: ЛУЧШИЙ вариант — ключ доступа сообщества (Управление → Работа с API → Создать
ключ; права: «Создание публикаций» + «Фотографии», не истекает). Подойдёт и токен
пользователя Standalone scope wall,photos,offline. Секреты: VK_ACCESS_TOKEN, VK_GROUP_ID
(числовой id сообщества, БЕЗ минуса — скрипт минусует сам).
"""
import json, os, datetime, urllib.request, urllib.parse, ssl

API = "https://api.vk.com/method"
V = "5.199"
SITE = "Полные разборы: https://znak-sudby.ru"
BOT = os.path.dirname(os.path.abspath(__file__))


def api(method, params, token):
    params = dict(params, access_token=token, v=V)
    req = urllib.request.Request(
        f"{API}/{method}",
        data=urllib.parse.urlencode(params).encode(), method="POST")
    with urllib.request.urlopen(req, timeout=30, context=ssl._create_unverified_context()) as r:
        out = json.loads(r.read().decode())
    if "error" in out:
        raise RuntimeError(f"{method}: {out['error'].get('error_msg')}")
    return out["response"]


def queue_text(date_str):
    q = json.load(open(os.path.join(BOT, "vk_queue.json"), encoding="utf-8"))
    dd = int(date_str[:2])
    item = q[(dd - 1) % len(q)]
    text = item["text"] if isinstance(item, dict) else item
    if not text.rstrip().endswith(SITE):
        text = text.rstrip() + "\n\n" + SITE
    return text


def cover(date_str):
    prep = os.path.join(BOT, "img", f"next_cover_vk_{date_str[:5]}.png")
    if os.path.exists(prep):
        return prep
    try:
        import max_daily as md
        seed = int(date_str.replace(".", ""))
        import random
        n = random.Random(seed).randrange(22)
        name, _ = md.CARDS[n]
        return md._make_cover_pil("vk", date_str, name.upper(), "КАРТА ДНЯ", "/tmp/vk_cover.png")
    except Exception as e:
        print("WARN обложка недоступна:", repr(e)[:120])
        return None


def upload_photo(path, token, group_id):
    up = api("photos.getWallUploadServer", {"group_id": group_id}, token)
    import subprocess
    out = subprocess.run(["curl", "-s", "-X", "POST", up["upload_url"],
                          "-F", f"photo=@{path};type=image/png"],
                         capture_output=True, text=True, timeout=120)
    saved = json.loads(out.stdout)
    res = api("photos.saveWallPhoto", {"group_id": group_id,
              "server": saved["server"], "photo": saved["photo"], "hash": saved["hash"]}, token)
    p = res[0]
    return f"photo{p['owner_id']}_{p['id']}"


def post(text, token, group_id, image_path=None):
    attachments = []
    if image_path:
        try:
            attachments.append(upload_photo(image_path, token, group_id))
        except Exception as e:
            print("WARN фото не загрузилось, пост текстом:", repr(e)[:120])
    params = {"owner_id": -int(group_id), "from_group": 1, "message": text,
              "signed": 0, "attachments": ",".join(attachments)}
    res = api("wall.post", params, token)
    return res.get("post_id")


def main():
    import sys
    date_str = datetime.date.today().strftime("%d.%m.%Y")
    # Свободный пост: env VK_CUSTOM_TEXT (GitHub Actions inputs) или 2-й аргумент CLI.
    custom = os.environ.get("VK_CUSTOM_TEXT", "").strip()
    if len(sys.argv) > 2 and sys.argv[1] == "post" and sys.argv[2].strip():
        custom = sys.argv[2].strip()
    text = custom if custom else queue_text(date_str)
    if not text.rstrip().endswith(SITE):
        text = text.rstrip() + "\n\n" + SITE
    if len(sys.argv) > 1 and sys.argv[1] == "print":
        print(text, "\n" + "=" * 40, "\nдлина:", len(text))
        print("[cover]:", cover(date_str))
        return
    token, group_id = os.environ.get("VK_ACCESS_TOKEN"), os.environ.get("VK_GROUP_ID")
    if not (token and group_id):
        sys.exit("Нет VK_ACCESS_TOKEN/VK_GROUP_ID (GitHub Secrets)")
    pid = post(text, token, group_id, cover(date_str))
    print("OK posted vk", date_str, "post_id", pid, "(custom)" if custom else "(queue)")


if __name__ == "__main__":
    main()
