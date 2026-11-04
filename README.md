# lesnykh.ru

Персональный сайт и онлайн-резюме. Статика на GitHub Pages, без бэкенда и фреймворков.

## Откуда берётся контент

Единственный источник данных — `data/cv.json`: контакты, опыт, стек, образование и тексты
на двух языках (`{"ru": "…", "en": "…"}`). Всё остальное генерируется и руками не правится:

| Файл | Что это |
|---|---|
| `index.html`, `en/cv/index.html` | страницы резюме (ru, en) |
| `ru/cv/index.html` | редирект старого адреса на главную |
| `resume.json`, `resume.ru.json` | резюме в формате [JSON Resume](https://jsonresume.org/schema/) |
| `ilia-lesnykh.vcf` | визитка для контактов |
| `llms.txt`, `sitemap.xml`, `robots.txt` | для поисковых и AI-краулеров |
| `assets/og-ru.png`, `assets/og-en.png` | превью ссылки в мессенджерах |
| `resume-ru.pdf`, `resume-en.pdf` | печатные версии |

Внешний вид живёт в `templates/page.html` (разметка, синтаксис как у Twig: `{{ }}`, `{% for %}`,
`{% if %}`), `styles.css` (экран и печать) и `templates/og.html` (превью-картинка).

## Сборка

Нужны `python3` (стандартная библиотека, ничего ставить не надо) и Google Chrome для PDF и картинок.

```sh
python3 scripts/build.py              # всё сразу
python3 scripts/build.py --no-chrome  # только HTML и текстовые файлы, без PDF и картинок
```

Если Chrome стоит не по стандартному пути: `CHROME=/путь/к/chrome python3 scripts/build.py`.

Типичный цикл: поправить `data/cv.json` → собрать → проверить `index.html` в браузере
(страницы открываются прямо с диска) → закоммитить всё, включая сгенерированные файлы → `git push`.
GitHub Pages публикует ветку `master` как есть.

## Переезд на HTTPS

Адрес сайта задан один раз в `data/cv.json` → `site.url`. После включения HTTPS поменять его
на `https://lesnykh.ru` и пересобрать: canonical, sitemap, Open Graph, JSON-LD и vCard обновятся сами.
