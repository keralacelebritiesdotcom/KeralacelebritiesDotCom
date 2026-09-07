<?php
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');

$items = [];
$excluded = [
    'index.html',
    'actors.html',
    'directors.html',
    'singers.html',
    'television.html',
    'other-personalities.html'
];

function clean_text($text) {
    $text = html_entity_decode($text ?? '', ENT_QUOTES | ENT_HTML5, 'UTF-8');
    $text = preg_replace('/\s+/u', ' ', strip_tags($text));
    return trim($text);
}

function first_match($pattern, $html) {
    if (preg_match($pattern, $html, $m)) return clean_text($m[1]);
    return '';
}

function first_attr_match($pattern, $html) {
    if (preg_match($pattern, $html, $m)) return trim(html_entity_decode($m[1], ENT_QUOTES | ENT_HTML5, 'UTF-8'));
    return '';
}

function normalise_image($image, $slug) {
    $image = trim($image);
    if ($image === '') return '/celebrities/images/' . $slug . '.jpg';
    if (preg_match('#^(https?:)?//#i', $image)) return $image;
    if ($image[0] === '/') return $image;
    return '/celebrities/' . ltrim($image, './');
}

foreach ((glob(__DIR__ . '/*.html') ?: []) as $path) {
    $file = basename($path);
    $lower = strtolower($file);
    if (in_array($lower, $excluded, true)) continue;
    if (!preg_match('/^[a-z0-9][a-z0-9_-]*\.html$/i', $file)) continue;

    $raw = @file_get_contents($path);
    if ($raw === false || trim($raw) === '') continue;

    $slug = preg_replace('/\.html$/i', '', $file);

    // These are deliberately parsed without DOMDocument so the endpoint also works
    // on hosts where the PHP DOM extension is not installed.
    // The visible H1 is the cleanest display name.
    $name = first_match('/<h1\b[^>]*>(.*?)<\/h1>/is', $raw);
    if (!$name) $name = first_attr_match('/<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']*)["\']/i', $raw);
    if (!$name) $name = first_attr_match('/<meta[^>]+content=["\']([^"\']*)["\'][^>]+property=["\']og:title["\']/i', $raw);
    if (!$name) $name = first_match('/<title\b[^>]*>(.*?)<\/title>/is', $raw);
    if (!$name) $name = ucwords(str_replace(['-', '_'], ' ', $slug));
    $name = preg_replace('/\s*[|–—-]\s*KeralaCelebrities\.com.*$/iu', '', $name);
    $name = trim(preg_replace('/\s+/u', ' ', $name));

    $description = first_attr_match('/<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)["\']/i', $raw);
    if (!$description) $description = first_attr_match('/<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']description["\']/i', $raw);

    // Prefer the actual profile image, not og:image, because many pages use the
    // site logo for social sharing while the visible profile photo is elsewhere.
    $image = '';
    $image = first_attr_match('/<img[^>]+class=["\'][^"\']*profile-photo[^"\']*["\'][^>]+src=["\']([^"\']+)["\']/i', $raw);
    if (!$image) $image = first_attr_match('/<img[^>]+src=["\']([^"\']+)["\'][^>]+class=["\'][^"\']*profile-photo[^"\']*["\']/i', $raw);
    if (!$image) $image = first_attr_match('/<div[^>]+class=["\'][^"\']*profile-photo[^"\']*["\'][^>]*>\s*<img[^>]+src=["\']([^"\']+)["\']/is', $raw);
    if (!$image) $image = first_attr_match('/<img[^>]+src=["\']([^"\']*\/celebrities\/images\/[^"\']*)["\']/i', $raw);
    if (!$image) $image = '/celebrities/images/' . $slug . '.jpg';

    $items[] = [
        'file' => $file,
        'url' => '/celebrities/' . rawurlencode($file),
        'name' => $name,
        'description' => $description,
        'image' => normalise_image($image, $slug)
    ];
}

usort($items, function ($a, $b) { return strcasecmp($a['name'], $b['name']); });
echo json_encode($items, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
?>
