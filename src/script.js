// script.js — сценарий словами. Необязательный «каркас»: что не описано — автомат дозаполнит.
import { seedFromString } from './util.js';

// синонимы названий сцен
export const ALIASES = {
  window_rain: ['дождь', 'окно', 'дождьзаокном', 'rain'],
  cat_sleep: ['кот', 'котик', 'кошка', 'котспит', 'cat'],
  city_night: ['город', 'улица', 'city'],
  stars: ['звёзды', 'звезды', 'небо', 'ночь', 'stars', 'созвездия'],
  coffee: ['кофе', 'утро', 'завтрак', 'coffee'],
  bicycle: ['велосипед', 'поездка', 'bike', 'велик'],
  tree_swing: ['дерево', 'качели', 'двор', 'tree'],
  heart: ['сердце', 'пульс', 'heart'],
  boat: ['лодка', 'море', 'закат', 'sea'],
  balloon: ['шарик', 'шар', 'воздушныйшар', 'balloon'],
  flowers: ['цветы', 'растёт', 'растет', 'сад', 'flowers'],
  music: ['музыка', 'ноты', 'наушники', 'music'],
  dance: ['танец', 'танцую', 'dance'],
  todo: ['дела', 'список', 'деладел', 'todo', 'календарь'],
  cake: ['торт', 'праздник', 'деньрождения', 'cake'],
  pillow: ['финал', 'сон', 'подушка', 'конец', 'pillow'],
  snow: ['снег', 'снегопад', 'зима', 'snow'],
  fire: ['костёр', 'костер', 'огонь', 'fire'],
  road: ['дорога', 'путь', 'road', 'трасса'],
  stretch: ['потягивается', 'потянулась', 'утро2', 'stretch', 'просыпается'],
  my_photo: ['картинка', 'фото', 'полароид', 'мое фото', 'моё фото', 'photo'],
  my_trace: ['обводка', 'рисунок', 'мой рисунок', 'обведи', 'trace'],
  surf_stand: ['стойка', 'стоит', 'сёрфер', 'серфер', 'постер', 'surfer', 'стенд'],
  surf_push: ['отжимания', 'отжимается', 'качается', 'push'],
  surf_face: ['взгляд', 'лицо', 'смотрит', 'face'],
  surf_horizon: ['горизонт', 'далёкий', 'далекий', 'дали', 'horizon'],
  surf_wave: ['волна', 'гребень', 'наволне', 'wave'],
  surf_fly: ['полёт', 'полет', 'лечу', 'летит', 'fly'],
  surf_bot: ['робот', 'бот', 'robot'],
  surf_rest: ['отдых', 'отдыхает', 'тихий', 'сидит', 'rest'],
  surf_light: ['свет', 'портал', 'внутрисвета', 'сияние', 'light'],
};

export const SETTING_ALIASES = {
  стиль: 'profile', материал: 'profile', чем: 'profile', style: 'profile',
  бумага: 'paper', paper: 'paper',
  палитра: 'palette', цвета: 'palette', palette: 'palette',
  настроение: 'mood', mood: 'mood', время: 'mood',
  плотность: 'dens', density: 'dens',
  темп: 'bpm', bpm: 'bpm',
  переход: 'transition', transition: 'transition',
  вариант: 'seed', seed: 'seed', сид: 'seed',
};

export const PROFILES_RU = {
  карандаш: 'pencil', простой: 'pencil', графит: 'pencil', pencil: 'pencil',
  цветные: 'color', цветной: 'color', цветныекарандаши: 'color', color: 'color', карандаши: 'color',
  фломастер: 'marker', фломастеры: 'marker', маркер: 'marker', marker: 'marker',
  ручка: 'pen', шариковая: 'pen', чернила: 'pen', pen: 'pen',
  смешанная: 'mixed', смешанный: 'mixed', микс: 'mixed', mixed: 'mixed',
  мел: 'chalk', chalk: 'chalk',
};
export const PAPERS_RU = { тетрадь: 'notebook', линейка: 'notebook', notebook: 'notebook', чистый: 'plain', чистыйлист: 'plain', plain: 'plain', клетка: 'grid', grid: 'grid', крафт: 'kraft', kraft: 'kraft', тёмный: 'dark', темный: 'dark', dark: 'dark' };
export const MOODS_RU = { утро: 'morning', morning: 'morning', день: 'day', day: 'day', вечер: 'evening', evening: 'evening', ночь: 'night', night: 'night' };
export const PALETTES_RU = { тёплая: 'warm', теплая: 'warm', warm: 'warm', холодная: 'cool', cool: 'cool', яркая: 'bright', bright: 'bright', мягкая: 'mute', mute: 'mute', ночная: 'night', night: 'night' };

const norm = s => s.toLowerCase().replace(/[ёЁ]/g, 'е').replace(/[_\-–—.,!?]/g, ' ').replace(/\s+/g, ' ').trim();
const squash = s => norm(s).replace(/\s/g, '');

function findScene(text) {
  const s = squash(text), words = norm(text).split(' ');
  for (const [id, list] of Object.entries(ALIASES)) {
    if (list.some(a => squash(a) === s)) return { id, rest: '' };
  }
  for (const [id, list] of Object.entries(ALIASES)) {
    for (const a of list) {
      if (s.startsWith(squash(a))) return { id, rest: text.slice(text.toLowerCase().indexOf(a.toLowerCase().split(' ')[0]) + a.length) };
    }
  }
  for (const w of words) for (const [id, list] of Object.entries(ALIASES)) if (list.some(a => squash(a) === squash(w))) return { id, rest: '' };
  return null;
}

function parseTime(s) {
  s = s.trim();
  let m = s.match(/^(\d+):(\d+(?:[.,]\d+)?)$/);
  if (m) return (+m[1]) * 60 + parseFloat(m[2].replace(',', '.'));
  m = s.match(/^(\d+(?:[.,]\d+)?)(s|с|сек)?$/);
  if (m) return parseFloat(m[1].replace(',', '.'));
  return null;
}

// Разбор сценария. Возвращает настройки + список сцен (со временем или без).
export function parseScript(text, scenesById) {
  const out = { profile: null, paper: null, palette: null, mood: null, dens: null, bpm: null, transition: null, seed: null, entries: [], warnings: [] };
  const lines = String(text || '').split('\n');
  lines.forEach((raw, idx) => {
    let line = raw.trim();
    if (!line || line.startsWith('#') || line.startsWith('//')) return;
    // настройка: ключ: значение   или   ключ = значение
    const sm = line.match(/^([A-Za-zА-Яа-яЁё]+)\s*[:=]\s*(.+)$/);
    if (sm && SETTING_ALIASES[norm(sm[1])]) {
      const key = SETTING_ALIASES[norm(sm[1])];
      const val = sm[2].trim();
      {
        const v = squash(val);
        if (key === 'profile') out.profile = PROFILES_RU[v] || v;
        else if (key === 'paper') out.paper = PAPERS_RU[v] || v;
        else if (key === 'palette') out.palette = PALETTES_RU[v] || v;
        else if (key === 'mood') out.mood = MOODS_RU[v] || v;
        else if (key === 'dens') out.dens = parseFloat(v) || null;
        else if (key === 'bpm') out.bpm = parseFloat(v) || null;
        else if (key === 'transition') out.transition = v;
        else if (key === 'seed') { const n = parseInt(v, 10); out.seed = Number.isFinite(n) ? n : seedFromString(v); }
      }
      return;
    }
    // строка-настройка из одного слова: «вечер», «карандаш», «клетка»
    const one = squash(line);
    if (MOODS_RU[one] && !findScene(line)) { out.mood = MOODS_RU[one]; return; }
    if (PROFILES_RU[one] && !findScene(line)) { out.profile = PROFILES_RU[one]; return; }
    if (PAPERS_RU[one] && !findScene(line)) { out.paper = PAPERS_RU[one]; return; }
    if (PALETTES_RU[one] && !findScene(line)) { out.palette = PALETTES_RU[one]; return; }
    // сцена: «название 0:24» / «название 0:24-0:40» / «название»
    const parts = line.split(/[\s]+/);
    const scene = findScene(line);
    if (!scene) { out.warnings.push(`строка ${idx + 1}: не знаю сцену «${line}»`); return; }
    let rest = line.replace(/^\S+\s*/, '');
    const params = {};
    const pc = rest.match(/свеч[а-я]*\s*[:=]?\s*(\d+)/i);
    if (pc) { params.candles = +pc[1]; rest = rest.replace(pc[0], ' '); }
    const capM = line.match(/^[A-Za-zА-Яа-яЁё]+\s*[:=]\s*(.+)$/);
    // подпись может стоять рядом со временем: «картинка: это Эйси! 0:12-0:22»
    if (capM && (scene.id === 'my_photo' || scene.id === 'my_trace')) params.caption = capM[1]
      .replace(/(\d+:\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?(?:s|с|сек)?)\s*(?:-|—|–|до|\.\.)\s*(\d+:\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?(?:s|с|сек)?)?/, ' ')
      .replace(/\s{2,}/g, ' ').trim();
    const times = rest.match(/(\d+:\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?(?:s|с|сек)?)\s*(?:-|—|–|до|\.\.)\s*(\d+:\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?(?:s|с|сек)?)?/);
    let t0 = null, t1 = null;
    if (times) {
      t0 = parseTime(times[1]);
      t1 = times[2] ? parseTime(times[2]) : null;
    } else {
      const single = rest.match(/(\d+:\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?(?:s|с|сек)?)/);
      if (single) t0 = parseTime(single[1]);
    }
    out.entries.push({ id: scene.id, t0, t1, params, line: idx + 1 });
  });
  return out;
}

export function sceneListText() {
  return Object.entries(ALIASES).map(([id, a]) => `${id}: ${a.slice(0, 3).join(', ')}`).join('\n');
}
