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

foreach ((glob(__DIR__ . '/*.html') ?: []) as $path) {
    $file = basename($path);
    if (in_array(strtolower($file), $excluded, true)) continue;
    if (!preg_match('/^[a-z0-9][a-z0-9_-]*\.html$/i', $file)) continue;

    $raw = @file_get_contents($path);
    if ($raw === false) continue;

    libxml_use_internal_errors(true);
    $doc = new DOMDocument();
    @$doc->loadHTML('<?xml encoding="UTF-8">' . $raw);
    libxml_clear_errors();
    $xp = new DOMXPath($doc);

    $slug = preg_replace('/\.html$/i', '', $file);

    $name = '';
    $q = $xp->query('//meta[@property="og:title"]/@content');
    if ($q && $q->length) $name = trim($q->item(0)->nodeValue);
    if (!$name) {
        $q = $xp->query('//h1');
        if ($q && $q->length) $name = trim($q->item(0)->textContent);
    }
    if (!$name) {
        $q = $xp->query('//title');
        if ($q && $q->length) $name = trim($q->item(0)->textContent);
    }
    if (!$name) $name = ucwords(str_replace(['-', '_'], ' ', $slug));
    $name = preg_replace('/\s*[|–—-]\s*KeralaCelebrities\.com.*$/iu', '', $name);
    $name = trim(preg_replace('/\s+/u', ' ', $name));

    $description = '';
    $q = $xp->query('//meta[@name="description"]/@content');
    if ($q && $q->length) $description = trim($q->item(0)->nodeValue);
    if (!$description) {
        $q = $xp->query('//main//p');
        if ($q && $q->length) {
            foreach ($q as $node) {
                $candidate = trim(preg_replace('/\s+/u', ' ', $node->textContent));
                if ($candidate !== '') { $description = $candidate; break; }
            }
        }
    }

    $image = '';
    $q = $xp->query('//meta[@property="og:image"]/@content');
    if ($q && $q->length) $image = trim($q->item(0)->nodeValue);
    if (!$image) {
        $q = $xp->query('//img[contains(@src,"/celebrities/images/")]/@src');
        if ($q && $q->length) $image = trim($q->item(0)->nodeValue);
    }
    if (!$image) {
        $q = $xp->query('//img/@src');
        if ($q && $q->length) $image = trim($q->item(0)->nodeValue);
    }
    if (!$image) $image = '/celebrities/images/' . $slug . '.jpg';
    elseif (!preg_match('#^https?://#i', $image) && $image[0] !== '/')
        $image = '/celebrities/' . ltrim($image, './');

    $items[] = [
        'file' => $file,
        'url' => '/celebrities/' . rawurlencode($file),
        'name' => $name,
        'description' => $description,
        'image' => $image
    ];
}

usort($items, function ($a, $b) { return strcasecmp($a['name'], $b['name']); });
echo json_encode($items, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
?>
