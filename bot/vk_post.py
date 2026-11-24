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
        print("WARN PIL обложка недоступна:", repr(e)[:120])
    try:
        pure_png_cover("/tmp/vk_cover.png", date_str)
        return "/tmp/vk_cover.png"
    except Exception as e:
        print("WARN fallback обложка:", repr(e)[:120])
        return None


def pure_png_cover(path, date_str):
    """Обложка БЕЗ PIL (чистый python + zlib): ночное небо, звёзды, восьмиконечная звезда."""
    import random, struct, zlib
    W, H = 1280, 768
    rnd = random.Random(int(date_str.replace(".", "")))
    top, bot = (9, 12, 34), (26, 18, 58)
    px = bytearray(W * H * 3)
    for y in range(H):
        t = y / (H - 1)
        row = bytes([int(top[0] + (bot[0] - top[0]) * t),
                     int(top[1] + (bot[1] - top[1]) * t),
                     int(top[2] + (bot[2] - top[2]) * t)]) * W
        px[y * W * 3:(y + 1) * W * 3] = row

    def set(x, y, rgb):
        if 0 <= x < W and 0 <= y < H:
            i = (y * W + x) * 3
            px[i:i + 3] = bytes(rgb)

    for _ in range(110):
        x, y = rnd.randrange(W), rnd.randrange(H)
        c = rnd.choice([(235, 238, 255), (255, 236, 180), (200, 210, 255)])
        for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            set(x + dx, y + dy, c)
    cx, cy, R = W // 2, H // 2 - 20, 185
    q = int(R * 0.70)
    for y in range(cy - R, cy + R + 1):
        dy = y - cy
        for x in range(cx - R, cx + R + 1):
            dx = x - cx
            if (abs(dx) + abs(dy) <= R) or (abs(dx) <= q and abs(dy) <= q):
                d = (dx * dx + dy * dy) ** 0.5 / R
                col = (255, 224, 130) if d < 0.45 else ((244, 196, 84) if d < 0.8 else (226, 176, 66))
                set(x, y, col)
    for k, w in ((0, 300), (1, 200), (2, 120)):
        y = cy + R + 40 + k * 26
        x0 = cx - w // 2
        for x in range(x0, x0 + w):
            fade = int(120 * (1 - abs(x - cx) / (w / 2)) ** 2)
            set(x, y, (190, 160, 90) if fade < 60 else (230, 200, 120))

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    raw = bytearray()
    for y in range(H):
        raw.append(0)
        raw += px[y * W * 3:(y + 1) * W * 3]
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
           + chunk(b"IEND", b""))
    open(path, "wb").write(png)


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


def preloaded_photo(date_str, group_id):
    """Фото, заранее загруженные в группу вручную: bot/img/photo_ids.json {"дд.мм": "456239017"}.
    Возврат attachment-строки photo-<group>_<id> (фото принадлежит группе)."""
    p = os.path.join(BOT, "img", "photo_ids.json")
    if os.path.exists(p):
        try:
            pid = json.load(open(p, encoding="utf-8")).get(date_str[:5])
            if pid:
                return pid if pid.startswith("photo") else f"photo-{group_id}_{pid}"
        except Exception as e:
            print("WARN photo_ids.json:", repr(e)[:80])
    return None


def post(text, token, group_id, image_path=None, photo_id=None):
    attachments = []
    if photo_id:
        attachments.append(photo_id)
    elif image_path:
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
    test_del = os.environ.get("VK_DELETE_POST_ID", "").strip()
    if test_del:
        print("DELETE post:", api("wall.delete",
              {"owner_id": -int(group_id), "post_id": test_del}, token))
        return
    test_attach = os.environ.get("VK_TEST_ATTACH", "").strip()
    pre = preloaded_photo(date_str, group_id)
    pid = post(text, token, group_id, cover(date_str), pre or (test_attach or None))
    if test_attach:
        print("TEST_ATTACH used:", test_attach)
    print("OK posted vk", date_str, "post_id", pid,
          "(custom)" if custom else "(queue)", "| фото:",
          "заранее загруженное" if pre else ("тест-attachment" if test_attach else "upload/нет"))


if __name__ == "__main__":
    main()
