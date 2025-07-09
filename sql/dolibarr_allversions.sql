--
-- Script run when an upgrade of Dolibarr is done. Whatever is the Dolibarr version.

-- Remove legacy constant from previous module name
DELETE FROM llx_const WHERE name = 'MAIN_MODULE_TEST';
--
