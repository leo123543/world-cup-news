const https = require('https');

const SOURCES = [
  { url: 'https://feeds.bbci.co.uk/sport/football/rss.xml', name: 'BBC Sport' },
  { url: 'https://www.theguardian.com/football/rss', name: 'The Guardian' },
  { url: 'https://www.skysports.com/rss/12040', name: 'Sky Sports' },
];

const TEAMS = [
  'Argentina','Brazil','France','England','Spain','Germany','Portugal',
  'Netherlands','Belgium','Croatia','Morocco','USA','United States',
  'Mexico','Canada','Uruguay','Colombia','Ecuador','Japan','South Korea',
  'Australia','Senegal','Nigeria','Ivory Coast','Saudi Arabia','Iran',
  'Serbia','Switzerland','Denmark','Poland','Wales','Hungary','Turkey',
  'Romania','Scotland','Austria','Ukraine','Algeria','Tunisia','Cameroon',
  'Egypt','Costa Rica','Jamaica','Panama','Bolivia','Chile','Peru',
  'Paraguay','Venezuela','New Zealand','Qatar','Ghana','Bahrain',
];

// Each pad is exactly 16 words — guarantees SM headline is 16-20 words for any title
const SM_PADS = [
  'in a significant moment at the FIFA World Cup 2026 as football nations compete for glory',
  'amid all the drama at the FIFA World Cup 2026 as the tournament reaches its climax',
  'as the FIFA World Cup 2026 enters its most dramatic and exciting knockout stage this summer',
  'with all the action from the FIFA World Cup 2026 as football fans worldwide watch closely',
];

const VIRAL_BOOST = {
  'record': 4, 'historic': 4, 'shock': 4, 'stunning': 4, 'eliminated': 4,
  'final': 3, 'semi-final': 3, 'semifinal': 3, 'penalty': 3, 'injury': 3,
  'controversial': 3, 'red card': 3, 'sacked': 3, 'hat-trick': 3, 'hat trick': 3,
  'breaking': 2, 'exclusive': 2, 'winner': 2, 'brace': 2, 'fired': 2,
  'goal': 1, 'victory': 1, 'defeat': 1, 'draw': 1,
};

const STARS = [
  'messi','ronaldo','mbappe','haaland','neymar','bellingham',
  'vinicius','yamal','pedri','kane','lewandowski','salah','de bruyne',
  'rodri','modric','griezmann','rashford','saka',
];

function fetchUrl(url, redirects = 0) {
  return new Promise((resolve, reject) => {
    if (redirects > 3) return reject(new Error('Too many redirects'));
    const req = https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0 WorldCupNews/1.0' } }, res => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return fetchUrl(res.headers.location, redirects + 1).then(resolve).catch(reject);
      }
      let data = '';
      res.setEncoding('utf8');
      res.on('data', c => (data += c));
      res.on('end', () => resolve(data));
    });
    req.on('error', reject);
    req.setTimeout(6000, () => { req.destroy(); reject(new Error('Timeout')); });
  });
}

function getTag(block, tag) {
  const re = new RegExp(`<${tag}[^>]*>(?:<!\\[CDATA\\[([\\s\\S]*?)\\]\\]>|([\\s\\S]*?))<\\/${tag}>`, 'i');
  const m = block.match(re);
  if (!m) return '';
  return (m[1] ?? m[2] ?? '')
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").trim();
}

function stripTags(s) {
  return s.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim();
}

function parseItems(xml, source) {
  return [...xml.matchAll(/<item>([\s\S]*?)<\/item>/g)].map(m => {
    const b = m[1];
    const title = stripTags(getTag(b, 'title'));
    const link = getTag(b, 'link') || getTag(b, 'guid');
    const description = stripTags(getTag(b, 'description')).slice(0, 220);
    const pubDate = getTag(b, 'pubDate');
    return title && link ? { title, link, description, pubDate, source } : null;
  }).filter(Boolean);
}

function detectTeams(title, desc) {
  const text = title + ' ' + desc;
  return TEAMS.filter(team => new RegExp(`\\b${team}\\b`, 'i').test(text));
}

function toSMHeadline(title, padIdx) {
  const clean = title
    .replace(/\s*[-–|]\s*(BBC Sport|Guardian|Sky Sports|ESPN)[^\s]*/gi, '')
    .replace(/^(WATCH|VIDEO|GALLERY|QUIZ|EXCLUSIVE):\s*/i, '')
    .trim();

  const words = clean.split(/\s+/).filter(Boolean);

  if (words.length >= 16 && words.length <= 20) return words.join(' ');
  if (words.length > 20) return words.slice(0, 20).join(' ');

  // Pad with a fixed 16-word WC context phrase to guarantee 16-20 word output
  const pad = SM_PADS[padIdx % SM_PADS.length].split(/\s+/);
  const combined = [...words, ...pad];
  return combined.slice(0, Math.min(20, combined.length)).join(' ');
}

function viralityScore(item) {
  const text = (item.title + ' ' + item.description).toLowerCase();
  const ageHours = (Date.now() - new Date(item.pubDate).getTime()) / 3_600_000;

  const recency = Math.max(0, 40 * (1 - ageHours / 12));
  const sourceScore = { 'BBC Sport': 15, 'The Guardian': 12, 'Sky Sports': 10 }[item.source] || 8;

  let kw = 0;
  for (const [word, pts] of Object.entries(VIRAL_BOOST)) {
    if (text.includes(word)) kw += pts;
  }

  const starScore = STARS.some(p => text.includes(p)) ? 10 : 0;
  const wcScore = ['world cup', '2026', 'fifa', 'copa'].some(k => text.includes(k)) ? 15 : 0;

  return recency + sourceScore + Math.min(kw, 20) + starScore + wcScore;
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=60');
  res.setHeader('Access-Control-Allow-Origin', '*');

  const results = await Promise.allSettled(
    SOURCES.map(s => fetchUrl(s.url).then(xml => parseItems(xml, s.name)))
  );

  let all = results.flatMap(r => (r.status === 'fulfilled' ? r.value : []));

  // 限定 12 小时内，不足 5 条则扩展到 24 小时
  const now = Date.now();
  let filtered = all.filter(i => now - new Date(i.pubDate).getTime() <= 12 * 3_600_000);
  if (filtered.length < 5) {
    filtered = all.filter(i => now - new Date(i.pubDate).getTime() <= 24 * 3_600_000);
  }

  const enriched = filtered.map((item, idx) => ({
    ...item,
    teams: detectTeams(item.title, item.description),
    smHeadline: toSMHeadline(item.title, idx),
    viralityScore: Math.round(viralityScore(item)),
  }));

  enriched.sort((a, b) => b.viralityScore - a.viralityScore);

  // 去重相似标题
  const seen = new Set();
  const items = enriched.filter(item => {
    const key = item.title.slice(0, 40).toLowerCase().replace(/\W/g, '');
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }).slice(0, 24);

  res.status(200).json({ items, fetchedAt: new Date().toISOString() });
};
