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
    for ext in (".png", ".gif"):
        prep = os.path.join(BOT, "img", f"next_cover_vk_{date_str[:5]}{ext}")
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
    """Картинка = GIF-документ сообщества: docs.getWallUploadServer → upload → docs.save.
    (photos.* с групповым ключом недоступны — проверено пробами 24.11.)"""
    up = api("docs.getWallUploadServer", {"group_id": int(group_id)}, token)
    res = multipart_upload(up["upload_url"], path, field="file")
    saved = api("docs.save", {"file": res["file"], "title": "Карта дня"}, token)
    d = saved[0] if isinstance(saved, list) else saved
    return f"doc{d['owner_id']}_{d['id']}"


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


def multipart_upload(url, path, field="photo"):
    """POST файла на upload-URL ВК (multipart/form-data) без curl."""
    import uuid
    b = uuid.uuid4().hex
    mime = "image/png" if path.endswith(".png") else "image/jpeg"
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"{field}\"; "
            f"filename=\"{os.path.basename(path)}\"\r\nContent-Type: {mime}\r\n\r\n").encode() \
           + open(path, "rb").read() + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req, timeout=120, context=ssl._create_unverified_context()) as r:
        return json.loads(r.read().decode())


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
    # Флаг-файл bot/img/test_msg.flag: "on" = тест messages-фото → стена;
    # число = удалить этот post_id; "off"/нет = обычная публикация.
    flag = os.path.join(BOT, "img", "test_msg.flag")
    if os.path.exists(flag):
        fval = open(flag, encoding="utf-8").read().strip()
        if fval == "on":
            img = os.path.join(BOT, "img", "test_msg_card.png")
            try:
                up = api("photos.getMessagesUploadServer", {"group_id": int(group_id)}, token)
                print("1) getMessagesUploadServer: OK")
                res = multipart_upload(up["upload_url"], img)
                print("2) upload resp keys:", sorted(res.keys()))
                saved = api("photos.saveMessagesPhoto",
                            {"server": res["server"], "photo": res["photo"], "hash": res["hash"]}, token)
                ph = saved[0] if isinstance(saved, list) else saved
                att = f"photo{ph['owner_id']}_{ph['id']}"
                print("3) attachment:", att)
                pid = post("Тест автоматической картинки: бот загрузил её сам и прикрепил к посту. Сейчас удалю.",
                           token, group_id, None, att)
                print("4) wall.post OK post_id:", pid, "— проверь глазами, видна ли КАРТИНКА в посте")
            except Exception as e:
                print("TEST-MSG-PHOTO FAIL:", repr(e)[:250])
            return
        if fval == "on2":
            gid = int(group_id)
            album = None
            try:
                album = api("photos.createAlbum", {"title": "test-album-zs", "group_id": gid}, token)
                print("createAlbum OK album_id:", album["album_id"])
            except Exception as e:
                print("createAlbum FAIL:", repr(e)[:160])
            tests = [
                ("photos.getWallUploadServer", {"group_id": gid}),
                ("photos.getUploadServer", {"group_id": gid, "album_id": album["album_id"] if album else 0}),
                ("photos.getOwnerPhotoUploadServer", {"owner_id": -gid}),
                ("docs.getWallUploadServer", {"group_id": gid, "type": "post"}),
            ]
            for m, p in tests:
                try:
                    r = api(m, p, token)
                    print(m, "OK", str(r)[:130])
                except Exception as e:
                    print(m, "FAIL:", repr(e)[:160])
            return
        if fval == "on3":
            gid = int(group_id)
            up = None
            used = None
            for t in (None, "post", "photo", "doc", "video", "gif"):
                try:
                    p = {"group_id": gid}
                    if t:
                        p["type"] = t
                    up = api("docs.getWallUploadServer", p, token)
                    used = t
                    print("docs.getWallUploadServer OK with type", t, "| url:", str(up.get("upload_url"))[:60])
                    break
                except Exception as e:
                    print("docs type", t, "FAIL:", repr(e)[:130])
            gif = os.path.join(BOT, "img", "test_card.gif")
            if up and os.path.exists(gif):
                try:
                    res = multipart_upload(up["upload_url"], gif, field="file")
                    print("upload resp:", str(res)[:140])
                    saved = api("docs.save", {"file": res["file"], "title": "Карта дня"}, token)
                    d = saved[0] if isinstance(saved, list) else saved
                    att = f"doc{d['owner_id']}_{d['id']}"
                    print("docs attachment:", att)
                    pid = post("Тест: карта дня как GIF-документ. Сейчас удалю.", token, group_id, None, att)
                    print("wall.post OK post_id:", pid)
                except Exception as e:
                    print("docs.save/wall.post FAIL:", repr(e)[:220])
            return
        if fval.isdigit():
            print("DELETE:", api("wall.delete",
                  {"owner_id": -int(group_id), "post_id": fval}, token))
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
