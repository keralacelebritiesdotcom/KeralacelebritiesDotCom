<?php
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');

$items=[];
foreach((glob(__DIR__.'/movie-*.html')?:[]) as $path){
    $file=basename($path);
    if(!preg_match('/^movie-(\d+)\.html$/i',$file,$m)) continue;
    $number=(int)$m[1];

    $raw=@file_get_contents($path);
    if($raw===false) continue;

    libxml_use_internal_errors(true);
    $doc=new DOMDocument();
    @$doc->loadHTML('<?xml encoding="UTF-8">'.$raw);
    $xp=new DOMXPath($doc);

    $title='';
    $q=$xp->query('//meta[@property="og:title"]/@content');
    if($q->length)$title=trim($q->item(0)->nodeValue);
    if(!$title){$q=$xp->query('//h1');if($q->length)$title=trim($q->item(0)->textContent);}
    if(!$title){$q=$xp->query('//title');if($q->length)$title=trim($q->item(0)->textContent);}
    if(!$title)$title='Movie '.$number;
    $title=preg_replace('/\s*[|–—-]\s*KeralaCelebrities\.com.*$/iu','',$title);
    $title=preg_replace('/\s+/',' ',trim($title));

    $status='Now Running';
    $q=$xp->query('//*[contains(concat(" ",normalize-space(@class)," ")," movie-status ")]');
    if($q->length)$status=trim($q->item(0)->textContent);
    else{
        $q=$xp->query('//meta[@name="movie-status"]/@content');
        if($q->length)$status=trim($q->item(0)->nodeValue);
    }

    $image='';
    $q=$xp->query('//meta[@property="og:image"]/@content');
    if($q->length)$image=trim($q->item(0)->nodeValue);
    if(!$image){
        $q=$xp->query('//*[contains(concat(" ",normalize-space(@class)," ")," movie-poster ")]//img/@src');
        if($q->length)$image=trim($q->item(0)->nodeValue);
    }
    if(!$image)$image='/movies/images/movie-'.$number.'.jpg';
    elseif(!preg_match('#^https?://#i',$image)&&$image[0]!=='/')
        $image='/movies/'.ltrim($image,'./');

    $items[]=['file'=>$file,'number'=>$number,'title'=>$title,'status'=>$status,'image'=>$image];
}

usort($items,function($a,$b){return $a['number']<=>$b['number'];});
echo json_encode($items,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
?>
