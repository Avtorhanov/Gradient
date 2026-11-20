#!/usr/bin/env python3
"""Проверка стендов по разделу 7 плана «05-stendy»: шаги, темы, размеры, полный экран, крайние значения ползунков,
налезания подписей, скорость ползунка, свайп, движок (несколько ручек, переключатель), теория всех уроков,
скрытая ссылка #theory-N, автопрохождение задач (с открытой панелью «Стенд»), задачи и уроки без изменений по сравнению
с прошлой версией (поле задачи see не считается), подписи кнопок в одну строку (полный экран боком), панели «Стенд» всех задач с полем see (see — только в уроках
со стендом, и в каждом уроке со стендом есть задачи с see), «Продолжить» и урок с карты открываются теорией.
Запуск из корня репозитория: python3 tools/verify.py index.html <папка для кадров> [уроки через запятую, по умолчанию 1,2,3,4] [прошлый index.html]
Уроки с суффиксом «:tasks» (например 1,2,3,4,5,6,7,8,9,10,11,12,13,14:tasks) — без прогона стендов: сравнение, движок, теория,
автопрохождение и панели — около 10 минут.
Нужны Playwright для Python и Chrome (/usr/bin/google-chrome). Уроки 3,4 — около 5 минут, 6,7 — около 9 минут, 1,2,3,4 — около 9 минут,
8,9 — около 10 минут, 10 — около 7 минут, 11,12 — около 12 минут, 13,14 — около 12 минут, 15,16 — около 15 минут, 17,18 — около 15 минут (дольше 10 минут — запускать в фоне и читать вывод из файла).
Итог печатается в конце, полный список — <папка>/report.json.
Для новой сцены: дописать паузы шагов в WAITS (мс, по шагам — сколько длится анимация), id героя в HERO,
перебор ручек и прогон кнопок в sweep(); в autoplay — способ решить новые виды задач (уже есть: mc, tf, num, match, fill,
order, xread, fit, slope, lrrun, gd, wfit, relu, circle, chain, tokgoal, emb, softmax, temp, gen, attn, code с правками CODE_FIX).
Переключатель в sweep() — щелчок по [data-sw="<номер ручки>"][data-v="<значение>"]."""
import sys, json, asyncio, os
from playwright.async_api import async_playwright

HTML, OUT = sys.argv[1], sys.argv[2]
_ls = sys.argv[3] if len(sys.argv) > 3 else "1,2,3,4"
TASKS_ONLY = _ls.endswith(":tasks")
LESSONS_TO_CHECK = [int(x) for x in _ls.replace(":tasks", "").split(",")]
PREV = sys.argv[4] if len(sys.argv) > 4 else None
HERO = ["#c-bar", "#v-torso", "#t-car", "#d-man", "#s-man", "#j-man", "#k-man", "#e-man", "#o-man", "#u-man", "#m-man", "#n-man", "#p-man", "#q-man", "#g-man", "#l-man"]   # группа героя в сцене (у долины — родитель #v-torso)
os.makedirs(OUT, exist_ok=True)
URL = "file://" + os.path.abspath(HTML)
WAITS = {1: [2200, 7000, 4200, 10500, 6000, 12500, 7500], 2: [2400, 5000, 2400, 3000, 3000, 6000, 4500, 6500], 5: [2500]*8,
         3: [3600, 1200, 9600, 7000, 9800, 4800, 2800], 4: [3300, 2600, 2100, 3900, 2300, 5200, 2600, 4100],
         6: [6200, 2200, 2200, 5000, 4400, 14500, 8000, 1500], 7: [7000, 2800, 2000, 2000, 5800, 8500, 1500, 4800],
         8: [2200, 4200, 1200, 800, 5200, 800, 6800, 7200], 9: [10000, 5200, 4000, 4400, 10500, 6200, 5600, 2200],
         10: [3300, 8600, 4200, 10400, 9800, 8200, 6200, 3000, 5400],
         11: [4200, 900, 10300, 14300, 900, 5500, 900, 5400], 12: [6000, 9600, 12600, 900, 17800, 3200, 7300, 9600],
         13: [14500, 4800, 11500, 6500, 1800, 5200, 3000], 14: [9800, 4600, 4300, 2000, 5000, 6400, 700],
         15: [4500, 3800, 2200, 2300, 4600, 5200, 2800], 16: [1700, 2000, 4000, 2500, 4700, 5700, 800, 2500],
         17: [1600, 8000, 21500, 14000, 16000, 8500, 10500, 6800], 18: [2700, 3300, 11500, 1800, 3900, 8600, 8200]}
# автопрохождение: правки кода в задачах с Python (Pyodide в проверке не грузится — задачу проверяет check.code)
CODE_FIX = {"L3T6": [("b = 20", "b = 50")], "L4T7": [("w, b = 10, 20", "w, b = 10, 10")], "L7T4": [("w += lr * dw", "w -= lr * dw"), ("b += lr * db", "b -= lr * db")],
            "L12T1": [("Value(2.0), Value(-3.0)", "Value(3.0), Value(-3.0)")]}
report = {"overlap": [], "errors": [], "notes": []}

OVERLAP_JS = r"""(HEROES) => {
  const svg = document.querySelector('#stScene svg'); if (!svg) return ['нет сцены'];
  const hidden = el => { for (let e = el; e && e !== svg.parentElement; e = e.parentElement){ const cs = getComputedStyle(e);
      if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity < 0.05) return true; } return false; };
  const texts = [...svg.querySelectorAll('text:not(.deco)')].filter(t => t.textContent.trim() && !hidden(t)).map(t => [t, t.getBoundingClientRect()]);
  const name = t => (t.id || t.textContent.trim().slice(0, 14));
  const hit = (a, b, p) => a.left < b.right - p && b.left < a.right - p && a.top < b.bottom - p && b.top < a.bottom - p;
  const out = [];
  for (let i = 0; i < texts.length; i++) for (let j = i + 1; j < texts.length; j++)
    if (hit(texts[i][1], texts[j][1], 1.5)) out.push('текст×текст: ' + name(texts[i][0]) + ' / ' + name(texts[j][0]));
  let hero = null; for (const h of HEROES){ const e = svg.querySelector(h); if (e){ hero = e.tagName === 'g' ? e : e.parentElement; break; } }
  if (hero) [...hero.children].filter(e => !hidden(e)).forEach(h => { const r = h.getBoundingClientRect();
    texts.forEach(([t, tr]) => { if (hit(r, tr, 1.5)) out.push('герой×текст: ' + name(t)); }); });
  const sr = svg.getBoundingClientRect(), fs = !!document.querySelector('.stand.fs');
  if (!fs) texts.forEach(([t, r]) => { if (r.left < sr.left - 2 || r.right > sr.right + 2 || r.top < sr.top - 2 || r.bottom > sr.bottom + 2) out.push('за краем: ' + name(t)); });
  return out;
}"""
SET_SL = "([i, v]) => { const s = document.querySelectorAll('[data-sl]')[i]; s.value = v; s.dispatchEvent(new Event('input', {bubbles:true})); }"
SET_SLS = "(vs) => { const ss = document.querySelectorAll('[data-sl]'); vs.forEach((v, i) => { if (v == null) return; ss[i].value = v; ss[i].dispatchEvent(new Event('input', {bubbles:true})); }); }"
VALS = "[...document.querySelectorAll('[id^=stV]')].map(e => e.textContent)"
# подписи кнопок: в одну строку (иначе в полном экране боком кнопка вырастает вдвое)
BTN_JS = """() => [...document.querySelectorAll('.st-acts button')].map(b => { const r = document.createRange(); r.selectNodeContents(b);
  const lines = new Set([...r.getClientRects()].map(x => Math.round(x.top))).size; return [b.textContent, lines, Math.round(b.getBoundingClientRect().height)]; })"""

async def new_page(b, w, h, theme, progress=None):
    ctx = await b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, color_scheme=theme, has_touch=True, is_mobile=True)
    page = await ctx.new_page()
    errs = []
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" and "ERR_FAILED" not in m.text and "ERR_NAME" not in m.text else None)
    page.on("pageerror", lambda e: errs.append(str(e)))
    await page.route("**/fonts.g*/**", lambda r: r.abort())
    await page.route("**/cdn.jsdelivr.net/**", lambda r: r.abort())
    await page.goto(URL + "#home")
    if progress is not None:
        await page.evaluate("p => { localStorage.setItem('nn-from-scratch-v2', JSON.stringify(p)); }", progress)
        await page.reload()
    return page, errs

async def check_ov(page, tag):
    r = await page.evaluate(OVERLAP_JS, HERO)
    for x in r: report["overlap"].append(f"{tag}: {x}")

async def watch(page, tag, ms, every=330):
    t = 0
    while t < ms:
        await page.wait_for_timeout(every); t += every
        await check_ov(page, tag)

async def sweep(page, lesson, tag):
    """Перебор ручек и прогон кнопок сцены — с проверкой налезаний на каждом кадре."""
    main = "light 390x844" in tag and "fs" not in tag   # заметки — только из одного прогона
    if lesson == 2:   # точка едет по графику: x от 20 до 30 при крайних w
        for v in ["-6", "14", "0", "0.5"]:
            await page.evaluate(SET_SL, [0, v])
            for k in range(7):
                await page.click("[data-act=plus]"); await page.wait_for_timeout(560)
                await check_ov(page, f"{tag} w={v} +1°×{k+1}")
    if lesson == 1:   # все температуры вечером, потом «Другая погода»
        for v in range(0, 36):
            await page.evaluate(SET_SL, [0, v]); await page.wait_for_timeout(40)
            await check_ov(page, f"{tag} x={v}")
        await page.click("[data-act=new]"); await watch(page, f"{tag} «Другая погода»", 9900)
    if lesson == 3:   # такси: все сочетания b и w у стойки (шаг 2, 0 км) и после поездок на 5, 8, 3, 6 км
        await page.click("#stNext"); await page.click("#stNext"); await page.wait_for_timeout(1500)
        for drive in range(5):
            if drive:
                await page.click("[data-act=go]"); await watch(page, f"{tag} «Поехали» №{drive}", 4400)
            km = await page.evaluate("document.querySelector('#stV2').textContent")
            for bv in range(0, 201, 20):
                for wv in range(0, 51, 5):
                    await page.evaluate(SET_SL, [0, bv]); await page.evaluate(SET_SL, [1, wv]); await page.wait_for_timeout(25)
                    await check_ov(page, f"{tag} {km} b={bv} w={wv}")
        await page.evaluate(SET_SL, [0, 100]); await page.evaluate(SET_SL, [1, 30])
        for k in range(3):
            await page.click("[data-act=seat]"); await watch(page, f"{tag} «Другая посадка» №{k+1}", 1400)
    if lesson == 4:   # дартс: все сочетания w и b, «Бросок», «Уменьшить L»
        for wi in range(7):
            for bv in range(15, 26):
                await page.evaluate(SET_SL, [0, round(9.7 + wi * 0.1, 1)]); await page.evaluate(SET_SL, [1, bv]); await page.wait_for_timeout(25)
                await check_ov(page, f"{tag} w={round(9.7 + wi * 0.1, 1)} b={bv}")
        await page.evaluate(SET_SL, [0, 10]); await page.evaluate(SET_SL, [1, 20])
        await page.click("[data-act=throw]"); await watch(page, f"{tag} «Бросок»", 5200, 200)
        await page.evaluate(SET_SL, [0, 10.3]); await page.evaluate(SET_SL, [1, 15])
        await page.click("[data-act=hot]"); await watch(page, f"{tag} «Уменьшить L»", 6000, 250)
        res = await page.evaluate("[document.querySelector('#stV0').textContent, document.querySelector('#stV1').textContent, document.querySelector('#stV3').textContent]")
        report["notes"].append(f"{tag}: «Уменьшить L» с w = 10,3, b = 15 привело к w = {res[0]}, b = {res[1]}, L = {res[2]}")
    if lesson == 6:   # долина, режим η: все η (след сразу), «Один шаг» до края и «▶ 10 шагов»
        for k in range(1, 31):
            v = round(k * 0.05, 2)
            await page.evaluate(SET_SL, [0, v]); await page.wait_for_timeout(30)
            await check_ov(page, f"{tag} η={v}")
        for v in ["0.25", "0.9", "1.1", "1.5"]:
            await page.evaluate(SET_SL, [0, v]); await page.wait_for_timeout(60)
            await page.click("[data-act=run]"); await watch(page, f"{tag} η={v} «10 шагов»", 6500, 250)
            for k in range(3):
                await page.click("[data-act=jump]"); await watch(page, f"{tag} η={v} «Один шаг» №{k+1}", 900, 150)
        res = await page.evaluate(VALS)
        report["notes"].append(f"{tag}: плашки после прогона: {res}")
    if lesson == 7:   # тир: все η (сразу итог), «Круг» по шагам, «▶ Обучить» при η = 0,25, 0,5, 0,9 и 1,1
        for k in range(1, 23):
            v = round(k * 0.05, 2)
            await page.evaluate(SET_SL, [0, v]); await page.wait_for_timeout(30)
            await check_ov(page, f"{tag} η={v}")
        await page.evaluate(SET_SL, [0, 0.25])
        for k in range(3):
            await page.click("[data-act=cycle]"); await watch(page, f"{tag} «Круг» №{k+1}", 6400, 200)
        for v in ["0.25", "0.5", "0.9", "1.1"]:
            await page.evaluate(SET_SL, [0, v]); await page.wait_for_timeout(60)
            await page.click("[data-act=train]"); await watch(page, f"{tag} η={v} «Обучить»", 13500 if v == "0.9" else 9000, 300)
            res = await page.evaluate(VALS)
            report["notes"].append(f"{tag}: «Обучить» при η = {v}: плашки {res}")
    if lesson == 8:   # жюри: ползунки x₁, w₁, x₂, w₂ (порядок в ctrl) — сочетания вкладов, «Голосуем», «Следующий» по кругу
        for w1 in [0, 1, 3, 8, 10]:
            for w2 in [0, 1, 3, 10]:
                for x1 in [0, 1, 2, 4, 6, 8, 10]:
                    for x2 in [0, 1, 5, 10]:
                        await page.evaluate(SET_SLS, [x1, w1, x2, w2]); await page.wait_for_timeout(20)
                        await check_ov(page, f"{tag} x₁={x1} w₁={w1} x₂={x2} w₂={w2}")
        await page.evaluate(SET_SLS, [5, 8, 7, 3])
        await page.click("[data-act=vote]"); await watch(page, f"{tag} «Голосуем»", 6200, 200)
        for k in range(3):
            await page.click("[data-act=next]"); await watch(page, f"{tag} «Следующий» №{k+1}", 4800, 200)
            res = await page.evaluate(VALS)
            report["notes"].append(f"{tag}: «Следующий» №{k+1}: плашки {res}")
    if lesson == 9:   # кран: все w и b при нажиме 5, «Качать», потом два крана — то же при нажиме 6, и обратно один
        async def grid(t):
            for wi in range(17):
                for bi in range(21):
                    await page.evaluate(SET_SLS, [round(-2 + wi * 0.25, 2), round(-6 + bi * 0.5, 1)]); await page.wait_for_timeout(15)
                    await check_ov(page, f"{t} w={round(-2 + wi * 0.25, 2)} b={round(-6 + bi * 0.5, 1)}")
        await grid(f"{tag} один кран, x=5")
        await page.evaluate(SET_SLS, [1, -2])
        await page.click("[data-act=pump]"); await watch(page, f"{tag} «Качать»", 4600, 200)
        await page.click("[data-act=two]"); await watch(page, f"{tag} «Второй кран»", 4600, 200)
        btn = await page.evaluate("document.querySelector('[data-act=two]').textContent")
        res = await page.evaluate(VALS)
        report["notes"].append(f"{tag}: после «Второй кран» кнопка «{btn}», плашки {res}")
        await grid(f"{tag} два крана, x=6")
        await page.evaluate(SET_SLS, [1, -2])
        await page.click("[data-act=two]"); await watch(page, f"{tag} «Один кран»", 4600, 200)
    if lesson == 10:   # бригада: «Все разом» по всем 8 точкам, при каждой — все N ползунком; «По очереди»; точки примера (шаг 3)
        for k in range(8):
            await page.click("[data-act=all]"); await watch(page, f"{tag} «Все разом» №{k+1}", 3600, 300)
            for n in range(1, 7):
                await page.evaluate(SET_SL, [0, n]); await page.wait_for_timeout(30)
                await check_ov(page, f"{tag} точка №{k+1} N={n}")
            if main:
                res = await page.evaluate("[document.querySelector('#stV1').textContent, document.querySelector('#stV2').textContent, document.querySelector('#e-bt').textContent]")
                report["notes"].append(f"{tag}: точка {res[0]}, N = 6: h = {res[1]}, старший: {res[2]}")
        accs = []
        for n in range(1, 7):
            await page.evaluate(SET_SL, [0, n]); await page.wait_for_timeout(30)
            accs.append(await page.evaluate("document.querySelector('#stV3').textContent"))
        if main: report["notes"].append(f"{tag}: угадано при N = 1…6: {accs}")
        await page.click("[data-act=one]"); await watch(page, f"{tag} «По очереди»", 7000, 300)
        for k in range(6): await page.click("#stPrev")
        await watch(page, f"{tag} шаг 3 снова", 4200, 350)
        for k in range(4):
            await page.click("[data-act=all]"); await watch(page, f"{tag} пример «Все разом» №{k+1}", 2600, 300)
            if main:
                res = await page.evaluate(VALS)
                report["notes"].append(f"{tag}: пример, кнопка №{k+1}: плашки {res}")
        await page.click("[data-act=one]"); await watch(page, f"{tag} пример «По очереди»", 3400, 300)
    if lesson == 11:   # трибуна: все a ползунком (проверка), «Вперёд» и семь «Шаг назад» при a = 0, 2, 4; восьмой — заново
        for k in range(41):
            v = round(k * 0.1, 1)
            await page.evaluate(SET_SL, [0, v]); await page.wait_for_timeout(25)
            await check_ov(page, f"{tag} a={v}")
            if main and v in (0, 2.1, 4):
                report["notes"].append(f"{tag}: a = {v}: доска «{await page.evaluate('document.querySelector(\"#o-t4\").textContent')}», плашки {await page.evaluate(VALS)}")
        for v in ["0", "2", "4"]:
            await page.evaluate(SET_SL, [0, v]); await page.wait_for_timeout(60)
            await page.click("[data-act=fwd]"); await watch(page, f"{tag} a={v} «Вперёд»", 3900, 250)
            for k in range(8):
                await page.click("[data-act=back]"); await watch(page, f"{tag} a={v} «Шаг назад» №{k+1}", 2100 if k else 2500, 200)
                if main and v == "2":
                    res = await page.evaluate("[document.querySelector('#o-t2').textContent, document.querySelector('#o-t3').textContent, ...[...document.querySelectorAll('[id^=stV]')].map(e => e.textContent)]")
                    report["notes"].append(f"{tag}: «Шаг назад» №{k+1}: доска {res[:2]}, плашки {res[2:]}")
    if lesson == 12:   # бухгалтер: все a ползунком; backward() дважды без zero_grad (копится), zero_grad(), четыре прохода подряд при a = 4 и 0,5
        for k in range(9):
            v = k * 0.5
            await page.evaluate(SET_SL, [0, v]); await page.wait_for_timeout(40)
            await check_ov(page, f"{tag} a={v}")
            if main: report["notes"].append(f"{tag}: a = {v}: плашки {await page.evaluate(VALS)}, облачко «{await page.evaluate('document.querySelector(\"#u-b2\").textContent')}»")
        await page.evaluate(SET_SL, [0, 2]); await page.wait_for_timeout(60)
        await page.click("[data-act=zero]"); await watch(page, f"{tag} «zero_grad()»", 3300, 250)
        for k in range(2):
            await page.click("[data-act=bw]"); await watch(page, f"{tag} «backward()» №{k+1}", 10800, 250)
            if main: report["notes"].append(f"{tag}: «backward()» №{k+1}: плашки {await page.evaluate(VALS)}")
        await page.click("[data-act=zero]"); await watch(page, f"{tag} «zero_grad()» после двух", 3300, 250)
        if main: report["notes"].append(f"{tag}: после «zero_grad()»: плашки {await page.evaluate(VALS)}")
        for v in ["4", "0.5"]:
            await page.evaluate(SET_SL, [0, v]); await page.wait_for_timeout(60)
            for k in range(3):
                await page.click("[data-act=bw]"); await watch(page, f"{tag} a={v} «backward()» №{k+2}", 10800, 300)
            if main: report["notes"].append(f"{tag}: a = {v}, четыре прохода: плашки {await page.evaluate(VALS)}, карточки {await page.evaluate('[...document.querySelectorAll(\"[id^=u-kg]\")].map(e => e.textContent)')}")
            await page.click("[data-act=zero]"); await watch(page, f"{tag} a={v} «zero_grad()»", 3300, 300)
    if lesson == 13:   # телеграф: оба текста × три способа резки (сразу итог), «✂ Резать» в каждом способе, «Ещё текст»
        for t in range(2):
            for m in ["s", "p", "w"]:
                await page.click(f"[data-sw='0'][data-v='{m}']"); await page.wait_for_timeout(120)
                await check_ov(page, f"{tag} текст {t + 1}, режем {m}")
                if main: report["notes"].append(f"{tag}: текст {t + 1}, режем {m}: плашки {await page.evaluate(VALS)}, телеграмма «{await page.evaluate('document.querySelector(\"#m-tl\").textContent')}»")
                await page.click("[data-act=cut]"); await watch(page, f"{tag} текст {t + 1}, режем {m}, «✂ Резать»", 13500 if m == "s" else 7000, 250)
            await page.click("[data-act=txt]"); await watch(page, f"{tag} «Ещё текст» №{t + 1}", 14500, 300)
    if lesson == 14:   # карта: каждое слово переключателем, «Стрелка» от него, «▶ Обучить» (два раза — разные случайные старты)
        for v in ["7", "11", "2", "5"]:
            await page.click(f"[data-sw='0'][data-v='{v}']"); await page.wait_for_timeout(120)
            await check_ov(page, f"{tag} слово {v}")
            await page.click("[data-act=arrow]"); await watch(page, f"{tag} слово {v}, «Стрелка»", 2600, 200)
            if main: report["notes"].append(f"{tag}: слово {v}, после «Стрелки»: плашки {await page.evaluate(VALS)}")
        for k in range(2):
            await page.click("[data-act=train]"); await watch(page, f"{tag} «Обучить» №{k + 1}", 6800, 250)
            if main: report["notes"].append(f"{tag}: «Обучить» №{k + 1}: плашки {await page.evaluate(VALS)}")
    if lesson == 15:   # театр: все места ползунком, «Поменять» (ест подсаживается рядом), «▶ Садимся», снова «Поменять» и ползунок
        for v in range(8):
            await page.evaluate(SET_SL, [0, v]); await page.wait_for_timeout(40)
            await check_ov(page, f"{tag} место {v}")
            if main: report["notes"].append(f"{tag}: место {v}: плашки {await page.evaluate(VALS)}")
        for k in range(2):
            await page.click("[data-act=swap]"); await watch(page, f"{tag} «Поменять» №{k + 1}", 1500, 200)
            if main: report["notes"].append(f"{tag}: «Поменять» №{k + 1}: плашки {await page.evaluate(VALS)}, карточка «{await page.evaluate('document.querySelector(\"#p-k1\").textContent')} | {await page.evaluate('document.querySelector(\"#p-k2\").textContent')}»")
        await page.click("[data-act=sit]"); await watch(page, f"{tag} «Садимся»", 4200, 200)
        if main: report["notes"].append(f"{tag}: после «Садимся»: плашки {await page.evaluate(VALS)}, карточка «{await page.evaluate('document.querySelector(\"#p-k1\").textContent')} | {await page.evaluate('document.querySelector(\"#p-k2\").textContent')}»")
        for v in [3, 7]:
            await page.evaluate(SET_SL, [0, v]); await page.wait_for_timeout(60)
            await page.click("[data-act=swap]"); await watch(page, f"{tag} место {v}, «Поменять»", 1800, 200)
    if lesson == 16:   # шумомер: сочетания трёх оценок ползунками (шаг 1), «▶ Хлопаем», «Всем +1» трижды
        for a in range(-3, 4):
            for b in range(-3, 4):
                for c in range(-3, 4):
                    await page.evaluate(SET_SLS, [a, b, c]); await page.wait_for_timeout(15)
                    await check_ov(page, f"{tag} оценки {a}, {b}, {c}")
            if main: report["notes"].append(f"{tag}: оценки {a}, 3, 3: плашки {await page.evaluate(VALS)}, шумомер «{await page.evaluate('[0,1,2].map(i => document.querySelector(\"#q-sl\" + i).textContent).join(\" | \")')}»")
        await page.evaluate(SET_SLS, [2, 0, 0]); await page.wait_for_timeout(60)
        await page.click("[data-act=clap]"); await watch(page, f"{tag} «Хлопаем»", 7200, 250)
        if main: report["notes"].append(f"{tag}: «Хлопаем» при 2, 0, 0: плашки {await page.evaluate(VALS)}")
        for k in range(3):
            await page.click("[data-act=plus]"); await watch(page, f"{tag} «Всем +1» №{k + 1}", 1200, 200)
            if main: report["notes"].append(f"{tag}: «Всем +1» №{k + 1}: плашки {await page.evaluate(VALS)}")

    if lesson == 17:   # клавиатура: все T ползунком, «▶ Пишем» при T = 0,3, 1 и 2, «Ещё буква» подряд
        for k in range(2, 21):
            await page.evaluate(SET_SL, [0, round(k / 10, 1)]); await page.wait_for_timeout(30)
            await check_ov(page, f"{tag} T={k / 10}")
            if main and k in (3, 10, 15, 20): report["notes"].append(f"{tag}: T = {k / 10}: плашки {await page.evaluate(VALS)}")
        for v in ["0.3", "1", "2"]:
            await page.evaluate(SET_SL, [0, v]); await page.wait_for_timeout(60)
            await page.click("[data-act=write]"); await watch(page, f"{tag} T={v} «Пишем»", 9500, 250)
            if main: report["notes"].append(f"{tag}: T = {v}, «Пишем»: плашки {await page.evaluate(VALS)}")
        for k in range(6):
            await page.click("[data-act=one]"); await watch(page, f"{tag} «Ещё буква» №{k + 1}", 3800, 250)
        if main: report["notes"].append(f"{tag}: после «Ещё буквы»: плашки {await page.evaluate(VALS)}, имена «{await page.evaluate('document.querySelector(\"#g-rb\").textContent')}»")
    if lesson == 18:   # библиотека: каждое слово-запрос, «▶ Ищем» для каждого, «Голова» по кругу
        for v in ["0", "1", "2"]:
            await page.click(f"[data-sw='0'][data-v='{v}']"); await page.wait_for_timeout(120)
            await check_ov(page, f"{tag} запрос {v}")
            if main: report["notes"].append(f"{tag}: запрос {v}: плашки {await page.evaluate(VALS)}, тетрадь «{await page.evaluate('document.querySelector(\"#l-n1\").textContent')}»")
            await page.click("[data-act=find]"); await watch(page, f"{tag} запрос {v}, «Ищем»", 7500, 250)
        for k in range(4):
            await page.click("[data-act=head]"); await watch(page, f"{tag} «Голова» №{k + 1}", 2800, 200)
            if main: report["notes"].append(f"{tag}: «Голова» №{k + 1}: плашки {await page.evaluate(VALS)}, кнопка «{await page.evaluate('document.querySelector(\"[data-act=head]\").textContent')}»")

async def run_steps(b, lesson, theme, w, h, fs=False):
    tag = f"L{lesson} {theme} {w}x{h}{' fs' if fs else ''}"
    page, errs = await new_page(b, w, h, theme)
    await page.evaluate(f"location.hash = '#theory-{lesson}'")
    await page.wait_for_timeout(300)
    if fs:
        await page.click("#stFs"); await page.wait_for_timeout(300)
        btn = await page.evaluate(BTN_JS)
        if any(x[1] > 1 for x in btn): report["errors"].append(f"{tag}: подпись кнопки в две строки: {btn}")
    n = await page.evaluate("document.querySelectorAll('#stDots i').length")
    for i in range(n):
        if i: await page.click("#stNext")
        # во время анимации проверяем налезания несколько раз
        await watch(page, f"{tag} шаг {i+1}", WAITS.get(lesson, [5000] * 10)[i], 350)
        if await page.query_selector("#stBk") and await page.evaluate("getComputedStyle(document.querySelector('#stBk')).visibility") == "visible" and lesson != 5 and not fs and w < 500 and theme == "light":
            await page.click("#stBk"); await page.wait_for_timeout(150)
            await (await page.query_selector("#stand")).screenshot(path=f"{OUT}/L{lesson}_{theme}_{w}_s{i+1}_book.png")
            await page.click("#stBk")
        shot = f"{OUT}/L{lesson}_{theme}_{w}{'_fs' if fs else ''}_s{i+1}.png"
        if fs or w > 500: await page.screenshot(path=shot)
        else: await (await page.query_selector("#stand")).screenshot(path=shot)
    # крайние значения каждой ручки
    rng = await page.evaluate("[...document.querySelectorAll('[data-sl]')].map(s => [s.min, s.max])")
    for si, (mn, mx) in enumerate(rng):
        for v in [mn, mx]:
            await page.evaluate(SET_SL, [si, v]); await page.wait_for_timeout(120)
            await check_ov(page, f"{tag} ползунок {si+1} = {v}")
            if not fs and w < 500: await (await page.query_selector("#stand")).screenshot(path=f"{OUT}/L{lesson}_{theme}_{w}_slider{si+1}_{v}.png")
    if lesson != 5: await sweep(page, lesson, tag)
    report["errors"] += [f"{tag}: {e}" for e in errs]
    await page.context.close()

async def engine_tests(b):
    page, errs = await new_page(b, 390, 844, "light")
    # 1) скорость ползунков: время отрисовки после input (обёртка над requestAnimationFrame)
    for lesson in sorted(set(LESSONS_TO_CHECK + [5])):
        await page.evaluate(f"location.hash = '#theory-{lesson}'"); await page.wait_for_timeout(500)
        res = await page.evaluate("""async () => {
          const out = [], raf = window.requestAnimationFrame;
          for (const s of document.querySelectorAll('[data-sl]')){
            const times = [];
            window.requestAnimationFrame = cb => raf(t => { const a = performance.now(); cb(t); times.push(performance.now() - a); });
            for (let i = 0; i < 60; i++){ s.value = +s.min + (s.max - s.min) * (i % 30) / 29; s.dispatchEvent(new Event('input', {bubbles:true})); await new Promise(r => raf(r)); }
            window.requestAnimationFrame = raf; times.sort((a, b) => a - b); out.push([times[Math.floor(times.length / 2)], times[times.length - 1]]);
          }
          return out; }""")
        for si, ms in enumerate(res):
            report["notes"].append(f"урок {lesson}, ползунок {si+1}: перерисовка медиана {ms[0]:.2f} мс, максимум {ms[1]:.2f} мс")
            if ms[0] > 1.0: report["errors"].append(f"урок {lesson}: перерисовка ползунка {si+1} {ms[0]:.2f} мс > 1 мс")
    # 2) свайп листает шаги
    await page.evaluate("location.hash = '#theory-1'"); await page.wait_for_timeout(400)
    n0 = await page.evaluate("document.querySelector('#stN').textContent")
    await page.evaluate("""() => { const c = document.querySelector('#stCap'), T = (x, y) => new Touch({identifier: 1, target: c, clientX: x, clientY: y});
      c.dispatchEvent(new TouchEvent('touchstart', {touches: [T(300, 200)], changedTouches: [T(300, 200)], bubbles: true}));
      c.dispatchEvent(new TouchEvent('touchend', {touches: [], changedTouches: [T(200, 205)], bubbles: true})); }""")
    n1 = await page.evaluate("document.querySelector('#stN').textContent")
    ta = await page.evaluate("getComputedStyle(document.querySelector('#stCap')).touchAction")
    report["notes"].append(f"свайп: «{n0}» → «{n1}», touch-action блока шагов: {ta}")
    if n0 == n1: report["errors"].append("свайп не листает шаги")
    # 3) движок: несколько ползунков и переключатель (временная тестовая сцена)
    res = await page.evaluate("""async () => {
      window.__sl = [];
      SCENES.__t = {vals: [["a","x","--sx"],["b","y","--sb",1]], acts: [["p","P"],["q","Q"]],
        ctrl: [{k:"w", min:0, max:10, col:"--sw"}, {k:"b", min:-5, max:5, step:1, col:"--sb"}, {k:"m", opts:[["s","буквы"],["t","слова"]], col:"--sx"}],
        svg: '<svg viewBox="0 0 360 200"></svg>', init(E){ return {draw(){}, step(s){ E.setCtrl("m", "t"); E.setCtrl("b", 3); }, slide(v, k){ window.__sl.push([k, String(v)]); }, action(){}}; }};
      const L = LESSONS[2], keep = L.stand; L.stand = {scene:"__t", steps:[{t:"1"},{t:"2"}]};
      location.hash = '#theory-3'; await new Promise(r => setTimeout(r, 400));
      const sls = [...document.querySelectorAll('[data-sl]')], sw = [...document.querySelectorAll('[data-sw]')];
      const init = [sls[1].value, sw.map(b => b.classList.contains('on'))];
      sls[0].value = 7; sls[0].dispatchEvent(new Event('input', {bubbles:true}));
      sls[1].value = -2; sls[1].dispatchEvent(new Event('input', {bubbles:true}));
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
      sw[0].click();
      const out = {n: sls.length, sw: sw.length, init, calls: window.__sl, on: sw.map(b => b.classList.contains('on')), tx: document.querySelector('#stV1').className,
                   colors: sls.map(s => getComputedStyle(s.closest('label')).color)};
      L.stand = keep; delete SCENES.__t; location.hash = '#home'; return out; }""")
    report["notes"].append("движок, тестовая сцена: " + json.dumps(res, ensure_ascii=False))
    ok = res["n"] == 2 and res["sw"] == 2 and ["w", "7"] in res["calls"] and ["b", "-2"] in res["calls"] and ["m", "s"] in res["calls"] and res["on"] == [True, False] and res["init"][0] == "3" and res["init"][1] == [False, True] and "tx" in res["tx"]
    if not ok: report["errors"].append("движок: несколько ручек / переключатель работают не так")
    # 4) ручки в две колонки (cols: 2 — сцена жюри): четыре ползунка парами в строку, кнопки во всю ширину
    if 8 in LESSONS_TO_CHECK:
        await page.evaluate("location.hash = '#theory-8'"); await page.wait_for_timeout(400)
        g = await page.evaluate("""() => { const r = e => e.getBoundingClientRect(), sl = [...document.querySelectorAll('.st-sl')].map(r), a = r(document.querySelector('.st-acts')), c = r(document.querySelector('.st-ctrl'));
          return {rows: [Math.round(sl[0].top) === Math.round(sl[1].top), Math.round(sl[2].top) === Math.round(sl[3].top), sl[2].top > sl[0].top], acts: Math.abs(a.width - c.width) < 2}; }""")
        report["notes"].append(f"ручки в две колонки (урок 8): {g}")
        if not (all(g["rows"]) and g["acts"]): report["errors"].append("урок 8: ручки не встали в две колонки")
    report["errors"] += [f"движок: {e}" for e in errs]
    await page.context.close()

async def all_theory(b, theme):
    page, errs = await new_page(b, 390, 844, theme)
    bad = []
    for i in range(1, 25):
        await page.evaluate(f"location.hash = '#theory-{i}'"); await page.wait_for_timeout(250)
        st = await page.evaluate("[!!document.querySelector('.need'), location.hash, !!document.querySelector('#stand'), !document.querySelector('.seg2') && !document.querySelector('#tt') && /Просмотр теории/.test(document.querySelector('.topbar').textContent)]")
        if not st[0] or st[1] != f"#theory-{i}": bad.append(i)
        if not st[3]: report["errors"].append(f"#theory-{i}: должна быть только теория — без вкладки «Задачи» и кнопки «К задачам», с пометкой «Просмотр теории»")
    # открытый урок по обычной ссылке после просмотра — снова с вкладками
    await page.evaluate("location.hash = '#lesson-1'"); await page.wait_for_timeout(250)
    if not await page.evaluate("!!document.querySelector('.seg2 [data-v=tasks]') && !!document.querySelector('#tt')"):
        report["errors"].append("#lesson-1 после #theory-N: нет вкладки «Задачи»")
    xp0 = await page.evaluate("localStorage.getItem('nn-from-scratch-v2')")
    if await page.evaluate("localStorage.getItem('nn-from-scratch-v2')") != xp0: report["errors"].append("просмотр теории изменил прогресс")
    # закрытый урок по обычной ссылке — на главную
    await page.evaluate("location.hash = '#lesson-7'"); await page.wait_for_timeout(250)
    h = await page.evaluate("location.hash")
    if h != "#home": report["errors"].append(f"#lesson-7 без прогресса открылся ({h})")
    if bad: report["errors"].append(f"теория не открылась: {bad}")
    stands = await page.evaluate("LESSONS.filter(L => L.stand).map(L => L.id)")
    report["notes"].append(f"теория всех 24 уроков ({theme}) открыта по #theory-N; стенды в уроках {stands}")
    report["errors"] += [f"теория {theme}: {e}" for e in errs]
    await page.context.close()

async def autoplay(b):
    """Проходит все задачи проверяемых уроков через интерфейс; уроки до них считаются решёнными.
    У задач с полем see перед решением открывается панель «Стенд» — она не должна мешать задаче."""
    p0, _ = await new_page(b, 390, 844, "light")
    pre = await p0.evaluate(f"(() => {{ const s = {{}}; LESSONS.slice(0, {min(LESSONS_TO_CHECK) - 1}).forEach(L => L.tasks.forEach(t => s[t.id] = {{h:0}})); return s; }})()")
    await p0.context.close()
    page, errs = await new_page(b, 390, 844, "light", {"v": 2, "xp": 0, "solved": pre, "srs": {}})

    async def type_num(a):
        s = str(a).replace("-", "−").replace(".", ",")
        if s.startswith("−"): await page.click(".keypad [data-k='−']"); s = s[1:]
        for ch in s: await page.click(f".keypad [data-k='{ch}']")

    for lesson in LESSONS_TO_CHECK:
        await page.evaluate(f"location.hash = '#lesson-{lesson}'"); await page.wait_for_timeout(300)
        await page.click(".seg2 [data-v=tasks]"); await page.wait_for_timeout(200)
        n = await page.evaluate(f"LESSONS[{lesson-1}].tasks.length")
        for k in range(n):
            t = await page.evaluate(f"(() => {{ const t = LESSONS[{lesson-1}].tasks[{k}]; return {{t: t.t, a: t.a, pairs: t.pairs, blanks: t.blanks, target: t.target, sol: t.sol, data: t.data, ctrl: t.ctrl, items: t.items, n: t.n, goal: t.goal, see: !!t.see}}; }})()")
            typ, tid = t["t"], f"L{lesson}T{k+1}"
            if t["see"]:
                await page.click("[data-tool=see]"); await page.wait_for_timeout(300)
            if typ in ("mc",):
                await page.click(f".opt[data-i='{t['a']}']")
            elif typ == "tf":
                await page.click(f".opt[data-v='{1 if t['a'] else 0}']")
            elif typ == "num":
                await type_num(t["a"])
                await page.click("[data-a=check]")
            elif typ == "chain":   # граф L = (a·b + c)·f: градиенты d, f, e, c, a, b по очереди
                for g in [-2, 4, -2, -2, 6, -4]:
                    await type_num(g); await page.click("#cn"); await page.wait_for_timeout(120)
            elif typ == "match":
                for i in range(len(t["pairs"])):
                    await page.click(f".mbtn[data-s=L][data-i='{i}']"); await page.click(f".mbtn[data-s=R][data-i='{i}']")
            elif typ == "fill":
                for i, bl in enumerate(t["blanks"]):
                    await page.click(f".blank[data-b='{i}']")
                    await page.evaluate("s => [...document.querySelectorAll('.chip')].find(c => c.textContent === s && !c.disabled).click()", bl)
                await page.click("[data-a=check]")
            elif typ == "xread":
                await page.evaluate("v => { const s = document.querySelector('#sx'); s.value = v; s.dispatchEvent(new Event('input')); }", (t["target"] - 20) / 10)
                await page.click("[data-a=check]")
            elif typ == "fit":   # данные W: w ≈ 12 (сдвиг задан); данные B: w = 10, b = 10
                wv, bv = (12, None) if t["data"] == "W" else (10, 10)
                await page.evaluate("([w, b]) => { const s = document.querySelector('#sw'), c = document.querySelector('#sb'); if (s){ s.value = w; s.dispatchEvent(new Event('input')); } if (c && b != null){ c.value = b; c.dispatchEvent(new Event('input')); } }", [wv, bv])
                await page.click("[data-a=check]")
            elif typ == "wfit":   # веса разбора: w₁ = 8, w₂ = 3
                await page.evaluate("() => { for (const [id, v] of [['#s1', 8], ['#s2', 3]]){ const s = document.querySelector(id); s.value = v; s.dispatchEvent(new Event('input')); } }")
                await page.click("[data-a=check]")
            elif typ == "relu":   # излом в x = 2, справа вверх: w = 1, b = −2
                await page.evaluate("() => { for (const [id, v] of [['#sw', 1], ['#sb', -2]]){ const s = document.querySelector(id); s.value = v; s.dispatchEvent(new Event('input')); } }")
                await page.click("[data-a=check]")
            elif typ == "circle":   # 6 нейронов, «Обучать», пока не угадано 95 %
                await page.click("#hs [data-h='6']"); await page.click("#go")
                for _ in range(60):
                    await page.wait_for_timeout(250)
                    if await page.evaluate("parseInt(document.querySelector('#acc').textContent) >= 95"): break
                report["notes"].append(f"{tid}: обучение круга — {await page.evaluate('document.querySelector(\"#ns\").textContent')} шагов, угадано {await page.evaluate('document.querySelector(\"#acc\").textContent')}")
                await page.click("[data-a=check]")
            elif typ == "order":
                for it in t["items"]:
                    await page.evaluate("s => [...document.querySelectorAll('.ord-pool .chip')].find(c => c.textContent === s && !c.disabled).click()", it)
            elif typ == "slope":   # шаг 0,5: раунд 1 с w = 6,5 — 9 раз «уменьшить», раунд 2 с w = −1,5 — 7 раз «увеличить»
                for _ in range(9): await page.click("#dl")
                for _ in range(7): await page.click("#dr")
            elif typ == "lrrun":   # η = 0,3: 10 шагов до дна
                await page.evaluate("() => { const s = document.querySelector('#se'); s.value = 4; s.dispatchEvent(new Event('input')); }")
                await page.click("#go"); await page.wait_for_timeout(2000)
                await page.click("[data-a=check]")
            elif typ == "gd":   # скорость 0,3 и шаги, пока ошибка не меньше 30
                await page.evaluate("() => { const s = document.querySelector('#lr'); s.value = 3; s.dispatchEvent(new Event('input')); for (let i = 0; i < 80; i++) document.querySelector('#s1').click(); }")
                await page.click("[data-a=check]")
            elif typ == "tokgoal":   # текст из подсказки: «мама мыла» — 5 разных букв (с пробелом)
                await page.fill("#tx", "мама мыла")
                await page.click("[data-a=check]")
            elif typ == "softmax":   # оценки кот, пёс, дом: «кот» больше 70 % — 2, 0, 0; почти поровну и все не меньше 2 — 2, 2, 2
                vals = [2, 0, 0] if t["goal"] == "cat" else [2, 2, 2]
                await page.evaluate("vs => vs.forEach((v, i) => { const s = document.querySelector('#z' + i); s.value = v; s.dispatchEvent(new Event('input')); })", vals)
                await page.click("[data-a=check]")
            elif typ == "temp":   # температура: меньше 0,3 — лидер больше 80 %, 1,5 и выше — лидер меньше 25 %
                await page.evaluate("v => { const s = document.querySelector('#tp'); s.value = v; s.dispatchEvent(new Event('input')); }", 0.3 if t["goal"] == "low" else 1.5)
                await page.click("[data-a=check]")
            elif typ == "gen":   # «Дописать 6 раз», пока не появится новое имя
                for _ in range(25):
                    await page.click("#gn"); await page.wait_for_timeout(60)
                    if await page.evaluate("[...document.querySelectorAll('.nm-chip.new')].some(e => e.textContent.length >= 4)"): break
                await page.click("[data-a=check]")
            elif typ == "attn":   # внимание: «она» больше всего смотрит на «Кошку»
                await page.click(".words button[data-i='0']")
            elif typ == "emb":   # карта смыслов: нажать нужное слово
                await page.click(f"svg g[data-w='{t['target']}']")
            elif typ == "code":
                code = await page.evaluate("document.querySelector('.editor textarea').value")
                for a, z in CODE_FIX.get(tid, []): code = code.replace(a, z)
                await page.evaluate("c => { const t = document.querySelector('.editor textarea'); t.value = c; t.dispatchEvent(new Event('input')); }", code)
                await page.click("[data-a=check]"); await page.wait_for_timeout(1500)
            await page.wait_for_timeout(250)
            solved = await page.evaluate(f"!!S.solved['{tid}']")
            if not solved:
                report["errors"].append(f"задача {tid} ({typ}) не решилась")
                break   # следующие задачи урока закрыты
            if k < n - 1: await page.click("[data-a=next]"); await page.wait_for_timeout(200)
    st = await page.evaluate("JSON.parse(localStorage.getItem('nn-from-scratch-v2'))")
    keys = sorted(k for k in st["solved"].keys() if int(k[1:].split("T")[0]) in LESSONS_TO_CHECK)
    report["notes"].append(f"автопрохождение: решено {len(keys)} задач проверяемых уроков: {', '.join(keys)}; XP {st['xp']}")
    report["errors"] += [f"задачи: {e}" for e in errs if "Python" not in e and "pyodide" not in e.lower()]
    await page.context.close()

async def see_panels(b):
    """Панели «Стенд» в окне задачи (поле see): see — только в уроках со стендом, в каждом уроке со стендом есть задачи с see
    (новый стенд приходит вместе с отсылками из задач урока); панель — на своём шаге, подпись короткая, ручек и плашек нет,
    кадр области = area, «Теория ↗» — в теорию на тот же шаг. Кадры: <папка>/see_L<урок>T<задача>_<тема>.png
    (тёмная тема — задачи с кадром области и первая в каждом уроке). Ещё: «Продолжить» на главной и «Открыть» на карте
    открывают урок теорией."""
    p0, _ = await new_page(b, 390, 844, "light")
    allp = await p0.evaluate("(() => { const s = {}; LESSONS.forEach(L => L.tasks.forEach(t => s[t.id] = {h:0})); return s; })()")
    cover = await p0.evaluate("LESSONS.map(L => [L.id, !!L.stand, L.tasks.filter(t => t.see).length, L.tasks.length])")
    await p0.context.close()
    stray = [f"L{i}" for i, st, n, _ in cover if n and not st]
    bare = [f"L{i}" for i, st, n, _ in cover if st and not n]
    if stray: report["errors"].append(f"поле see в уроках без стенда: {stray}")
    if bare: report["errors"].append(f"уроки со стендом без отсылок see из задач: {bare}")
    report["notes"].append("отсылки see по урокам со стендом (задач с see / всего): " + ", ".join(f"L{i} {n}/{t}" for i, st, n, t in cover if st))
    PANEL_JS = """() => { const p = document.querySelector('.tpanel'), n = p.querySelector('.st-n'), svg = p.querySelector('#stScene svg'), txt = p.querySelector('#stTxt'),
        ctl = p.querySelector('.st-ctrl'), vals = p.querySelector('.st-vals');
      return {vis: !p.hidden, mini: !!p.querySelector('.stand.mini'), n: n && n.textContent.trim(), vb: svg && svg.getAttribute('viewBox'),
        cap: txt ? txt.textContent : '', th: !!p.querySelector('.st-th'), hid: [ctl, vals].every(e => !e || getComputedStyle(e).display === 'none'),
        h: Math.round(p.getBoundingClientRect().height), wide: p.scrollWidth > p.clientWidth + 1}; }"""
    heights, n_ok = [], 0
    for theme in ["light", "dark"]:
        page, errs = await new_page(b, 390, 844, theme, {"v": 2, "xp": 0, "solved": allp, "srs": {}})
        items = await page.evaluate("LESSONS.filter(L => L.stand).flatMap(L => L.tasks.map((t, k) => t.see ? [L.id, k, t.see, L.stand.steps.length] : null).filter(Boolean))")
        seen = set()
        for lid, k, see, total in items:
            step = see if isinstance(see, int) else see["step"]
            area = None if isinstance(see, int) else see.get("area")
            first = lid not in seen; seen.add(lid)
            if theme == "dark" and not (area or first): continue
            tag = f"L{lid}T{k+1} {theme}"
            await page.evaluate(f"openLesson({lid}, 'tasks', {k})"); await page.wait_for_timeout(250)
            await page.click("[data-tool=see]"); await page.wait_for_timeout(2600)
            r = await page.evaluate(PANEL_JS)
            bad = []
            if not r["vis"] or not r["th"]: bad.append("панель или «Теория ↗» не видны")
            if not r["mini"] or not r["hid"]: bad.append("не короткий стенд (видны ручки или плашки)")
            if r["wide"]: bad.append("панель шире экрана")
            if r["n"] != f"Шаг {step} из {total}": bad.append(f"шаг «{r['n']}», нужен {step}")
            if not r["cap"].strip() or len(r["cap"]) > 220: bad.append(f"подпись {len(r['cap'])} знаков")
            if area and r["vb"] != " ".join(str(x) for x in area): bad.append(f"кадр {r['vb']}, нужен {area}")
            if theme == "light": heights.append((r["h"], f"L{lid}T{k+1}"))
            await (await page.query_selector("#task")).screenshot(path=f"{OUT}/see_L{lid}T{k+1}_{theme}.png")
            # «Теория ↗» — в теорию на тот же шаг, стенд на экране
            await page.click(".tpanel .st-th"); await page.wait_for_timeout(400)
            q = await page.evaluate("""() => { const on = document.querySelector('.seg2 [data-v=theory]').classList.contains('on'), n = document.querySelector('#standHost #stN');
                return [on, n && n.textContent.trim(), Math.round(document.querySelector('#standHost').getBoundingClientRect().top)]; }""")
            if not q[0]: bad.append("«Теория ↗» не открыла теорию")
            if q[1] != f"Шаг {step} из {total}": bad.append(f"теория открылась на «{q[1]}»")
            if not (-5 <= q[2] <= 150): bad.append(f"стенд теории не на экране (верх {q[2]} px)")
            if bad: report["errors"].append(f"панель {tag}: " + "; ".join(bad))
            else: n_ok += 1
        # в уроке без стенда кнопки нет, даже если поле see есть
        nost = await page.evaluate("(LESSONS.find(L => !L.stand) || {}).id")
        if nost:
            await page.evaluate(f"openLesson({nost}, 'tasks', 0)"); await page.wait_for_timeout(250)
            if await page.query_selector("[data-tool=see]"): report["errors"].append(f"урок {nost} без стенда: в задаче есть кнопка «Стенд»")
        report["errors"] += [f"панели {theme}: {e}" for e in errs]
        await page.context.close()
    heights.sort(reverse=True)
    report["notes"].append(f"панели «Стенд»: без замечаний {n_ok}; самые высокие (px): {heights[:5]}")
    # «Продолжить» и «Открыть» на карте — урок открывается теорией
    page, errs = await new_page(b, 390, 844, "light", {"v": 2, "xp": 0, "solved": {"L1T1": {"h": 0}}, "srs": {}})
    await page.click("#go"); await page.wait_for_timeout(300)
    a = await page.evaluate("[location.hash, document.querySelector('.seg2 [data-v=theory]').classList.contains('on')]")
    await page.evaluate("location.hash = '#home'"); await page.wait_for_timeout(300)
    await page.click("[data-open='1']"); await page.wait_for_timeout(300)
    c = await page.evaluate("[location.hash, document.querySelector('.seg2 [data-v=theory]').classList.contains('on')]")
    report["notes"].append(f"«Продолжить» → {a}, «Открыть» на карте → {c}")
    if a != ["#lesson-1", True]: report["errors"].append(f"«Продолжить» открыл не теорию: {a}")
    if c != ["#lesson-1", True]: report["errors"].append(f"урок с карты открылся не теорией: {c}")
    report["errors"] += [f"главная: {e}" for e in errs]
    await page.context.close()

async def compare_prev(b):
    """Задачи всех уроков и все поля уроков, кроме stand, — те же, что в прошлой версии (иначе собьётся прогресс).
    Поле задачи see (отсылка к теории) не считается: от него номера задач и прогресс не зависят."""
    JS = """() => { const f = (k, v) => typeof v === 'function' ? v.toString() : v;
      return [JSON.stringify(LESSONS.map(L => L.tasks.map(({see, ...t}) => t)), f), JSON.stringify(LESSONS.map(L => { const {stand, ...r} = L; return {...r, tasks: r.tasks.map(({see, ...t}) => t)}; }), f), LESSONS.length, LESSONS.reduce((s, L) => s + L.tasks.length, 0), LESSONS.reduce((s, L) => s + L.tasks.filter(t => t.see).length, 0)]; }"""
    out = []
    for path in [PREV, HTML]:
        ctx = await b.new_context(); page = await ctx.new_page()
        await page.route("**/fonts.g*/**", lambda r: r.abort()); await page.route("**/cdn.jsdelivr.net/**", lambda r: r.abort())
        await page.goto("file://" + os.path.abspath(path) + "#home"); out.append(await page.evaluate(JS)); await ctx.close()
    report["notes"].append(f"сравнение с прошлой версией: уроков {out[1][2]}, задач {out[1][3]} (с полем see — {out[1][4]}); задачи совпадают: {out[0][0] == out[1][0]}; уроки без stand совпадают: {out[0][1] == out[1][1]}")
    if out[0][0] != out[1][0]: report["errors"].append("задачи отличаются от прошлой версии")
    if out[0][1] != out[1][1]: report["errors"].append("поля уроков (кроме stand) отличаются от прошлой версии")

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        if PREV: await compare_prev(b)
        await engine_tests(b)
        await all_theory(b, "light"); await all_theory(b, "dark")
        await autoplay(b)
        await see_panels(b)
        jobs = []
        for lesson in ([] if TASKS_ONLY else LESSONS_TO_CHECK):
            for theme in ["light", "dark"]:
                jobs.append(run_steps(b, lesson, theme, 390, 844))
                jobs.append(run_steps(b, lesson, theme, 844, 390))
            jobs.append(run_steps(b, lesson, "light", 390, 844, fs=True))
            jobs.append(run_steps(b, lesson, "dark", 844, 390, fs=True))
        if 5 not in LESSONS_TO_CHECK: jobs.append(run_steps(b, 5, "light", 390, 844))   # пилот не сломан общими правками
        for i in range(0, len(jobs), 4): await asyncio.gather(*jobs[i:i+4])
        await b.close()
    ov = sorted(set(report["overlap"]))
    json.dump({**report, "overlap": ov}, open(os.path.join(OUT, "report.json"), "w"), ensure_ascii=False, indent=1)
    # одинаковые налезания (тот же урок и те же подписи) — одной строкой: сколько раз и первый пример
    groups = {}
    for o in ov:
        key = (o.split(" ", 1)[0], o[o.index(": ") + 2:])
        groups.setdefault(key, []).append(o)
    print("ЗАМЕТКИ:"); [print("  " + n) for n in report["notes"]]
    print(f"ОШИБКИ ({len(report['errors'])}):"); [print("  " + e) for e in report["errors"]]
    print(f"НАЛЕЗАНИЯ ({len(ov)}, разных — {len(groups)}; полный список — report.json):")
    for (les, what), lst in sorted(groups.items()): print(f"  {les} ×{len(lst)}: {what}   (например: {lst[0]})")

asyncio.run(main())
