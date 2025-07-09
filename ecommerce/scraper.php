<?php
/*
 * Simple page to run the Python image scraper
 */

$res = 0;
if (!$res && !empty($_SERVER["CONTEXT_DOCUMENT_ROOT"])) {
    $res = @include $_SERVER["CONTEXT_DOCUMENT_ROOT"]."/main.inc.php";
}
$tmp = empty($_SERVER['SCRIPT_FILENAME']) ? '' : $_SERVER['SCRIPT_FILENAME'];
$tmp2 = realpath(__FILE__);
$i = strlen($tmp) - 1;
$j = strlen($tmp2) - 1;
while ($i > 0 && $j > 0 && isset($tmp[$i]) && isset($tmp2[$j]) && $tmp[$i] == $tmp2[$j]) {
    $i--;
    $j--;
}
if (!$res && $i > 0 && file_exists(substr($tmp, 0, ($i + 1))."/main.inc.php")) {
    $res = @include substr($tmp, 0, ($i + 1))."/main.inc.php";
}
if (!$res && $i > 0 && file_exists(dirname(substr($tmp, 0, ($i + 1)))."/main.inc.php")) {
    $res = @include dirname(substr($tmp, 0, ($i + 1)))."/main.inc.php";
}
if (!$res && file_exists("../main.inc.php")) {
    $res = @include "../main.inc.php";
}
if (!$res && file_exists("../../main.inc.php")) {
    $res = @include "../../main.inc.php";
}
if (!$res) {
    die("Include of main fails");
}

require_once '../lib/ecommerce.lib.php';

$langs->loadLangs(array('ecommerce@ecommerce'));

$url = GETPOST('url', 'alpha');
$selector = GETPOST('selector', 'alpha');
$output = '';
if ($url) {
    $result = ecommerceRunScraper($url, $selector);
    $output = $result['output'];
}

llxHeader('', $langs->trans('ImageScraper'));

print load_fiche_titre($langs->trans('ImageScraper'));
print '<form method="POST" action="'.$_SERVER['PHP_SELF'].'">';
print '<div class="center">';
print $langs->trans('Url').': <input type="text" name="url" size="60" value="'.dol_escape_htmltag($url).'">';
print '<br>'.$langs->trans('CssSelector').': <input type="text" name="selector" value="'.dol_escape_htmltag($selector).'">';
print '<br><input type="submit" class="button" value="'.$langs->trans('Scrape').'">';
print '</div></form>';

if ($output) {
    print '<hr><pre>'.dol_escape_htmltag($output).'</pre>';
}

llxFooter();
$db->close();
