const https = require('https');

const SOURCES = [
  { url: 'https://feeds.bbci.co.uk/sport/football/rss.xml', name: 'BBC Sport' },
  { url: 'https://www.theguardian.com/football/rss', name: 'The Guardian' },
  { url: 'https://www.skysports.com/rss/12040', name: 'Sky Sports' },
];

const WC_KEYS = [
  'world cup', '2026', 'fifa', 'copa', 'wc26',
  'group stage', 'knockout', 'quarter', 'semi-final', 'final',
  'usa', 'canada', 'mexico', 'host',
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
  const re = new RegExp(
    `<${tag}[^>]*>(?:<!\\[CDATA\\[([\\s\\S]*?)\\]\\]>|([\\s\\S]*?))<\\/${tag}>`, 'i'
  );
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

function isWC(item) {
  const text = (item.title + ' ' + item.description).toLowerCase();
  return WC_KEYS.some(k => text.includes(k));
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=60');
  res.setHeader('Access-Control-Allow-Origin', '*');

  const results = await Promise.allSettled(
    SOURCES.map(s => fetchUrl(s.url).then(xml => parseItems(xml, s.name)))
  );

  let all = results.flatMap(r => (r.status === 'fulfilled' ? r.value : []));
  all.sort((a, b) => new Date(b.pubDate) - new Date(a.pubDate));

  // 优先展示世界杯相关，不足时用普通足球新闻补足
  const wc = all.filter(isWC);
  const rest = all.filter(i => !isWC(i));
  const items = (wc.length >= 8 ? wc : [...wc, ...rest]).slice(0, 24);

  res.status(200).json({ items, fetchedAt: new Date().toISOString() });
};
