#!/usr/bin/env python3
"""Ежедневные рубрики канала МАКС «Знак судьбы» для GitHub Actions.
Утро 9:00 МСК — «число ангела дня» (день месяца дважды, ядро = сумма цифр).
Вечер 19:00 МСК — «карта дня» (аркан по seed=ддммгггг, честный смысл).
Каждый пост идёт с ОБЛОЖКОЙ (PIL, рисуется в рантайме: число дня / аркан
прямо на картинке), картинка сверху, текст снизу. Тексты без обещаний
гарантий/диагнозов — уважение к читателю.
Публикация: POST /uploads?type=image -> PUT файла -> POST /messages?chat_id=...
с attachments [{"type":"image","payload":{"token":...}}].
"""
import json, os, random, ssl, subprocess, sys, urllib.request

MAX_API = "https://platform-api2.max.ru"
CTX = ssl._create_unverified_context()  # песочница не доверяет CA MAX; на runner безвредно

# --- ядро числа: короткие честные тексты ---
CORE = {
 1: ("новое начало", "сегодня хорошо начинать с малого — первый шаг важнее плана",
     "Что вы давно откладываете? Начните сегодня с 10 минут."),
 2: ("диалог и парность", "день про контакт: слушайте, договаривайтесь, не молчите",
     "Кому вы не сказали главного? Скажите сегодня."),
 3: ("слово и радость", "день про речь и творчество: говорите, пишите, создавайте",
     "Что вы хотите сказать вслух, но пока не сказали?"),
 4: ("опора и порядок", "день про фундамент: распорядок, дом, тело — укрепляйте базу",
     "Какая мелкая рутина укрепит ваш день?"),
 5: ("перемены и движение", "не держитесь за старое — движение сегодня полезнее стабильности",
     "Какой шаг вы боитесь сделать? Сделайте маленький."),
 6: ("забота и баланс", "день про семью, близость и тело: забота — не слабость",
     "О ком или о себе вы позаботитесь сегодня?"),
 7: ("тишина и смысл", "день про паузу: ответы приходят, когда вы не спешите",
     "Что вам говорит интуиция, если прислушаться?"),
 8: ("сила и дела", "день про завершение: закройте долг, доведите начатое, примите решение",
     "Какое «повисшее» дело вы закроете сегодня?"),
 9: ("завершение цикла", "день про отпускание: благодарите прошлое и освобождайте место новому",
     "Что пора отпустить? Напишите это и позвольте уйти."),
}

# --- 22 старших аркана: честные короткие смыслы ---
CARDS = {
 0: ("Шут", "начало пути без гарантий и тяжёлой поклажи. Доверие к дороге сильнее расчёта — сделайте шаг, который давно просится."),
 1: ("Маг", "инструменты уже в руках: слово, воля, навык. День для действия, а не для подготовки к действию."),
 2: ("Верховная Жрица", "день тишины и знания, которое ещё не сказано словами. Не форсируйте — наблюдайте, интуиция сегодня точнее логики."),
 3: ("Императрица", "плодородие: то, что вы вкладывали, начинает расти. Позаботьтесь о теле и о деле, которое вы «выращиваете»."),
 4: ("Император", "структура и границы: порядок снаружи даёт опору внутри. Скажите чёткое «да» и чёткое «нет»."),
 5: ("Иерофант", "традиция и учитель: день про опыт, который стоит перенять. Обратитесь к источнику, а не к яркой обёртке."),
 6: ("Влюблённые", "выбор сердцем: сегодня важнее решить, что ваше, чем угодить всем. Выбор из любви — самый лёгкий."),
 7: ("Колесница", "управление силами: воля держит вожжи. Направьте энергию на одну цель, а не на пять сразу."),
 8: ("Сила", "мягкая сила: терпение и доброта побеждают напор. Ласково приручите свою тревогу."),
 9: ("Отшельник", "время наедине с собой: ответ ищется в тишине, а не в чужих мнениях. Вечер — для уединения."),
 10: ("Колесо Фортуны", "цикл поворачивается: то, что уходило, возвращается в новом виде. Принимайте движение, а не цепляйтесь за спицу."),
 11: ("Справедливость", "честные весы: разберитесь с причинами, а не со следствиями. Ясность стоит непростого разговора."),
 12: ("Повешенный", "смена угла зрения: пауза — не поражение. Отпустите контроль на вечер и посмотрите иначе."),
 13: ("Смерть", "естественное завершение: что-то отработало своё. Не удерживайте — освобождается место для нового."),
 14: ("Умеренность", "алхимия середины: смешайте противоположности по чуть-чуть. Сегодня лечится балансом, а не рывком."),
 15: ("Дьявол", "смотрите на свои цепи честно: привычка, страх, зависимость. Осознать — уже наполовину отпустить."),
 16: ("Башня", "внезапное освобождение: рушится только то, что стояло на лжи. Берегите главное — людей и себя."),
 17: ("Звезда", "надежда после шторма: тихий свет, вера в путь. Сделайте маленькое доброе дело — и заметите, как отпустило."),
 18: ("Луна", "иллюзии и страхи в полумраке: сегодня факты важнее фантазий. Проверьте, что реально, прежде чем тревожиться."),
 19: ("Солнце", "ясность и тепло: день для открытости, благодарности и честной радости. Поделитесь светом."),
 20: ("Суд", "зов к обновлению: итоги и честная переоценка. Прислушайтесь к внутреннему зову — он про ваш следующий этап."),
 21: ("Мир", "завершение большого цикла: целостность и выход на новый круг. Поблагодарите путь — он вас вынес."),
}

SIG = "Разборы — на znak-sudby.ru | Канал «Знак судьбы»"


def angel_number_post(date_str: str):
    dd = date_str[:2].lstrip("0")
    shown = dd * 2                                   # 21 → 2121, 3 → 33
    core_n = sum(int(c) for c in shown)
    while core_n > 9:
        core_n = sum(int(c) for c in str(core_n))
    name, tip, question = CORE[core_n]
    tip = tip[0].upper() + tip[1:]
    text = (f"✦ Число ангела дня — {shown}\n\n"
            f"Ядро дня — {core_n}: {name}. {tip}.\n\n{question}\n\n{SIG}")
    return text, shown, core_n, name


def card_post(date_str: str):
    seed = int(date_str.replace(".", ""))
    n = random.Random(seed).randrange(22)
    name, text = CARDS[n]
    text = text[0].upper() + text[1:]
    full = (f"✦ Карта дня — {name}\n\n{text}\n\n"
            f"Один вопрос себе на вечер: где сегодня моя честность с собой?\n\n{SIG}")
    return full, name, n


# ---------- обложка ----------
def _font_path():
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img", "DejaVuSans-Bold.ttf")
    if os.path.exists(local):
        return local
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(p):
            return p
    raise FileNotFoundError("DejaVuSans-Bold.ttf не найден (шрифт должен лежать в bot/img/)")


def make_cover(mode: str, date_str: str, big: str, small: str, out: str = "/tmp/max_cover.png"):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:  # ubuntu runner: ставим сами, интернета хватает
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "pillow"], check=True)
        from PIL import Image, ImageDraw, ImageFont

    W, H = 1280, 720
    img = Image.new("RGB", (W, H), (23, 18, 43))
    d = ImageDraw.Draw(img)
    top, bottom = (23, 18, 43), (63, 37, 92)          # индиго -> фиолет
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    rng = random.Random(date_str + mode)
    for _ in range(150):                              # звёздное небо
        x, y = rng.randrange(W), rng.randrange(H)
        r = rng.choice((1, 1, 1, 2, 2, 3))
        v = rng.choice((90, 140, 200, 255))
        d.ellipse([x - r, y - r, x + r, y + r], fill=(v, v, min(255, v + 25)))
    cx, cy, R = W // 2, 350, 215                      # золотое кольцо
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=(214, 178, 74), width=4)
    d.ellipse([cx - R - 7, cy - R - 7, cx + R + 7, cy + R + 7], outline=(214, 178, 74), width=1)
    f_small = ImageFont.truetype(_font_path(), 46)
    f_big = ImageFont.truetype(_font_path(), 150 if len(big) <= 4 else 105)
    f_date = ImageFont.truetype(_font_path(), 30)

    def center(text, font, y, fill):
        d.text(((W - d.textlength(text, font=font)) / 2, y), text, font=font, fill=fill)

    center("· " + small + " ·", f_small, 92, (214, 178, 74))
    center(big, f_big, 268, (255, 243, 214))
    center(date_str, f_date, 626, (168, 152, 192))
    img.save(out)
    return out


def upload_cover(path: str, token: str) -> str:
    # 1) POST /uploads?type=image -> {url}; 2) POST multipart файла на url ->
    #    {"photos": {"0": {"token": ...}}}; 3) вернуть token для attachments.
    req = urllib.request.Request(f"{MAX_API}/uploads?type=image", method="POST",
                                 headers={"Authorization": token})
    with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
        up = json.loads(r.read().decode())
    out = subprocess.run(["curl", "-sk", "-X", "POST", up["url"],
                          "-F", f"file=@{path};type=image/png"],
                         capture_output=True, text=True, timeout=120)
    photos = json.loads(out.stdout)["photos"]
    return list(photos.values())[0]["token"]


def post_max(text: str, chat_id: str, token: str, image_path: str | None = None):
    body = {"text": text}
    if image_path:
        body["attachments"] = [{"type": "image", "payload": {"token": upload_cover(image_path, token)}}]
    req = urllib.request.Request(f"{MAX_API}/messages?chat_id={chat_id}",
                                 data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
        return json.loads(r.read().decode())


def main():
    import datetime
    arg = sys.argv[1] if len(sys.argv) > 1 else "print"
    date_str = datetime.date.today().strftime("%d.%m.%Y")
    if arg == "print":                                # локальная проверка текстов и обложек
        t1, shown, core_n, name = angel_number_post(date_str)
        t2, card, n = card_post(date_str)
        print(t1, "\n" + "=" * 40 + "\n", t2)
        print("[cover morning]:", make_cover("morning", date_str, shown, "ЧИСЛО АНГЕЛА ДНЯ", "/tmp/cover_morning.png"))
        print("[cover evening]:", make_cover("evening", date_str, card.upper(), "КАРТА ДНЯ", "/tmp/cover_evening.png"))
        return
    mode = arg
    if mode == "auto":                                # один workflow, два cron: по UTC-часу
        mode = "morning" if 5 <= datetime.datetime.utcnow().hour < 12 else "evening"
    chat_id, token = os.environ.get("MAX_CHAT_ID"), os.environ.get("MAX_BOT_TOKEN")
    if not (chat_id and token):
        sys.exit("Нет MAX_CHAT_ID/MAX_BOT_TOKEN (GitHub Secrets)")
    if mode == "morning":
        text, shown, core_n, name = angel_number_post(date_str)
        cover = make_cover(mode, date_str, shown, "ЧИСЛО АНГЕЛА ДНЯ")
    elif mode == "evening":
        text, card, n = card_post(date_str)
        cover = make_cover(mode, date_str, card.upper(), "КАРТА ДНЯ")
    else:
        sys.exit("mode: morning | evening | auto | print")
    post_max(text, chat_id, token, cover)
    print("OK posted", mode, date_str)


if __name__ == "__main__":
    main()
