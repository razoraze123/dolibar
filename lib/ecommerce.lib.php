<?php
/* Copyright (C) 2025		SuperAdmin
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

/**
 * \file    ecommerce/lib/ecommerce.lib.php
 * \ingroup ecommerce
 * \brief   Library files with common functions for Ecommerce
 */

/**
 * Prepare admin pages header
 *
 * @return array<array{string,string,string}>
 */
function ecommerceAdminPrepareHead()
{
	global $langs, $conf;

	// global $db;
	// $extrafields = new ExtraFields($db);
	// $extrafields->fetch_name_optionals_label('myobject');

	$langs->load("ecommerce@ecommerce");

	$h = 0;
	$head = array();

	$head[$h][0] = dol_buildpath("/ecommerce/admin/setup.php", 1);
	$head[$h][1] = $langs->trans("Settings");
	$head[$h][2] = 'settings';
	$h++;

	/*
	$head[$h][0] = dol_buildpath("/ecommerce/admin/myobject_extrafields.php", 1);
	$head[$h][1] = $langs->trans("ExtraFields");
	$nbExtrafields = is_countable($extrafields->attributes['myobject']['label']) ? count($extrafields->attributes['myobject']['label']) : 0;
	if ($nbExtrafields > 0) {
		$head[$h][1] .= ' <span class="badge">' . $nbExtrafields . '</span>';
	}
	$head[$h][2] = 'myobject_extrafields';
	$h++;
	*/

	$head[$h][0] = dol_buildpath("/ecommerce/admin/about.php", 1);
	$head[$h][1] = $langs->trans("About");
	$head[$h][2] = 'about';
	$h++;

	// Show more tabs from modules
	// Entries must be declared in modules descriptor with line
	//$this->tabs = array(
	//	'entity:+tabname:Title:@ecommerce:/ecommerce/mypage.php?id=__ID__'
	//); // to add new tab
	//$this->tabs = array(
	//	'entity:-tabname:Title:@ecommerce:/ecommerce/mypage.php?id=__ID__'
	//); // to remove a tab
	complete_head_from_modules($conf, $langs, null, $head, $h, 'ecommerce@ecommerce');

	complete_head_from_modules($conf, $langs, null, $head, $h, 'ecommerce@ecommerce', 'remove');

	return $head;
}

/**
 * Run the Python image scraper on the given URL.
 *
 * @param string $url Product page URL
 * @param string|null $selector Optional CSS selector
 * @return array{output:string,code:int}
 */
function ecommerceRunScraper(string $url, string $selector = null)
{
        $script = dol_buildpath('/ecommerce/scraper/scraper_images.py', 1);
        $cmd = 'python3 '.escapeshellarg($script).' '.escapeshellarg($url);
        if (!empty($selector)) {
                $cmd .= ' --selector '.escapeshellarg($selector);
        }
        $output = array();
        $ret = 0;
        @exec($cmd, $output, $ret);
        return array('output' => implode("\n", $output), 'code' => $ret);
}

