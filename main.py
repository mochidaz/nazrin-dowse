from flask import Flask, request, render_template, stream_template, send_from_directory, jsonify
import cloudscraper
from bs4 import BeautifulSoup
import urllib.parse
import json
from functools import lru_cache
from dataclasses import dataclass, asdict
from typing import Optional, Generator, Set, Dict, Any
import re

app = Flask(__name__, static_url_path='/media', static_folder='media')

WHITESPACE_CHARS = [
    '\u0020', '\u00A0', '\u1680', '\u2000', '\u2001', '\u2002', '\u2003',
    '\u2004', '\u2005', '\u2006', '\u2007', '\u2008', '\u2009', '\u200A',
    '\u202F', '\u205F', '\u3000'
]
WHITESPACE_PATTERN = re.compile('|'.join(map(re.escape, WHITESPACE_CHARS)))


@dataclass
class Track:
    album: str
    track_number: str
    arrangement_title: str
    translated_name: str
    arrangement: str
    source: str
    vocals: str
    original_title: str
    guitar: str
    note: str
    from_: str
    genre: str
    album_img: str
    lyrics: str = "-"
    lyrics_link: Optional[Dict[str, str]] = None

    def __post_init__(self):
        if self.album_img and not self.album_img.startswith('http'):
            self.album_img = f"https://en.touhouwiki.net{self.album_img}"


class ScraperSession:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.scraper = cloudscraper.create_scraper(
                browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
            )
        return cls._instance

    def get(self, url: str):
        try:
            response = self.scraper.get(url, timeout=30)
            response.raise_for_status()
            return response
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None


@lru_cache(maxsize=128)
def normalize_whitespace(text: str) -> str:
    text = WHITESPACE_PATTERN.sub(' ', text)
    return ' '.join(text.split()).strip()


def parse_track_info(track_element, base_url: str) -> Optional[Dict[str, Any]]:
    try:
        title_elem = track_element.find('b')
        if not title_elem:
            return None

        arrangement_title = title_elem.get_text(strip=True)
        track_number = "0"

        prev_sibling = title_elem.previous_sibling
        if prev_sibling and isinstance(prev_sibling, str):
            track_parts = prev_sibling.strip().split('.')
            if track_parts:
                track_number = track_parts[0]

        lyrics_link = None
        link_elem = title_elem.find('a')
        if link_elem and 'href' in link_elem.attrs:
            lyrics_link = {
                "link": urllib.parse.urljoin(base_url, link_elem['href']),
                "written": link_elem.get('class', [None])[0]
            }

        info_dict = {
            'original_title': set(),
            'arrangement': set(),
            'source': set(),
            'vocals': set(),
            'lyrics': set(),
            'guitar': set(),
            'note': set(),
            'from_': set(),
            'genre': set(),
            'translated_name': None
        }

        arrangement_info = [li.get_text(strip=True) for li in track_element.find_all('li')]

        for info in arrangement_info:
            info_lower = info.lower()

            if 'original title:' in info_lower:
                title = info.split('original title:', 1)[1].split('source:', 1)[0].strip()
                info_dict['original_title'].add(title.replace("\u3000", " "))
            elif 'guitar:' in info_lower:
                info_dict['guitar'].add(info.split('guitar:', 1)[1].strip())
            elif 'arrangement:' in info_lower:
                info_dict['arrangement'].add(info.split('arrangement:', 1)[1].strip())
            elif 'source:' in info_lower:
                info_dict['source'].add(info.split('source:', 1)[1].strip())
            elif 'vocals:' in info_lower:
                info_dict['vocals'].add(info.split('vocals:', 1)[1].strip())
            elif 'lyrics:' in info_lower:
                info_dict['lyrics'].add(info.split('lyrics:', 1)[1].strip())
            elif 'note:' in info_lower:
                info_dict['note'].add(info.split('note:', 1)[1].strip())
            elif 'from:' in info_lower:
                info_dict['from_'].add(info.split('from:', 1)[1].strip())
            elif 'genre:' in info_lower:
                info_dict['genre'].add(info.split('genre:', 1)[1].strip())

        ja_span = track_element.find('span', {'lang': 'ja'})
        if ja_span:
            translated_elem = ja_span.find_next('i')
            if translated_elem:
                translated_elem = translated_elem.find_next('i')
                if translated_elem:
                    info_dict['translated_name'] = translated_elem.get_text(strip=True)

        return {
            'track_number': track_number,
            'arrangement_title': arrangement_title,
            'lyrics_link': lyrics_link,
            'info': info_dict
        }
    except Exception as e:
        print(f"Error parsing track: {e}")
        return None


def search_generator(search_query: str, url: str, is_api: bool = False) -> Generator:
    scraper = ScraperSession()
    normalized_query = normalize_whitespace(search_query.lower())

    response = scraper.get(url)
    if not response:
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    rows = [row for row in soup.find_all('tr', valign='top') if row.find('a')]
    album_count = len(rows)

    print(f"Found {album_count} albums")
    if not is_api:
        yield f"0/{album_count}"

    for i, row in enumerate(rows):
        if not is_api:
            print(f"Processing album {i + 1}/{album_count}")
            yield f"{i + 1}/{album_count}"

        album_link = row.find('a')
        if not album_link:
            continue

        album_href = album_link.get('href')
        album_title = album_link.get('title', 'Unknown Album')
        album_img = row.find('img')
        album_image = album_img.get('src', '') if album_img else ''

        album_url = urllib.parse.urljoin(url, album_href)
        album_response = scraper.get(album_url)
        if not album_response:
            continue

        album_soup = BeautifulSoup(album_response.text, 'html.parser')
        album_text_normalized = normalize_whitespace(album_soup.text.lower())

        if normalized_query not in album_text_normalized:
            continue

        track_lists = album_soup.find_all('ul')
        for track_list in track_lists:
            track_list_text = normalize_whitespace(track_list.text.lower())
            if normalized_query not in track_list_text:
                continue

            tracks = track_list.find_all('li', recursive=False)
            for track in tracks:
                parsed = parse_track_info(track, url)
                if not parsed or not parsed['info']['original_title']:
                    continue

                original_titles_normalized = {
                    normalize_whitespace(t.lower()) for t in parsed['info']['original_title']
                }

                if not any(normalized_query in title for title in original_titles_normalized):
                    continue

                info = parsed['info']
                track_obj = Track(
                    album=album_title,
                    track_number=parsed['track_number'],
                    arrangement_title=parsed['arrangement_title'],
                    translated_name=info['translated_name'] or "-",
                    arrangement=", ".join(info['arrangement']) or "-",
                    source=", ".join(info['source']) or "-",
                    vocals=", ".join(info['vocals']) or "-",
                    original_title=", ".join(info['original_title']) or "-",
                    guitar=", ".join(info['guitar']) or "-",
                    note=", ".join(info['note']) or "-",
                    from_=", ".join(info['from_']) or "-",
                    genre=", ".join(info['genre']) or "-",
                    album_img=album_image,
                    lyrics=", ".join(info['lyrics']) or "-",
                    lyrics_link=parsed['lyrics_link']
                )

                if is_api:
                    track_dict = asdict(track_obj)
                    yield json.dumps({'count': i, 'data': track_dict}) + '\n'
                else:
                    yield track_obj


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form.get('url', '').strip()
        search_query = request.form.get('search_query', '').strip()

        if not url or not search_query:
            return render_template('index.html', error="URL and search query are required")

        def generate():
            count = 0
            for item in search_generator(search_query, url, is_api=False):
                if not isinstance(item, str):
                    count += 1
                yield item
            yield count

        return stream_template('results.html', tracks=generate())

    return render_template('index.html')


@app.route('/google1faec20f7ffb55d9.html')
def google_verification():
    return send_from_directory('templates', 'google1faec20f7ffb55d9.html')


@app.route('/media/<path:filename>')
def media(filename):
    return send_from_directory('media', filename)


@app.route("/api/search", methods=['GET'])
def api_search():
    url = request.args.get('url', '').strip()
    search_query = request.args.get('search_query', '').strip()

    if not url or not search_query:
        return jsonify({'error': 'URL and search_query parameters are required'}), 400

    def generate():
        for result in search_generator(search_query, url, is_api=True):
            yield result

    return app.response_class(generate(), mimetype='application/json')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)