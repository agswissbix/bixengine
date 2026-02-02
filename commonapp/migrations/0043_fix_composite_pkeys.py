from django.db import migrations

def fix_composite_pkeys_safe(apps, schema_editor):
    cursor = schema_editor.connection.cursor()
    
    # Lista delle tabelle con le relative colonne per la chiave composta
    tables_to_fix = {
        'sys_group_user': ['groupid', 'userid'],
        'sys_lookup_table_item': ['lookuptableid', 'itemcode'],
        'sys_table_feature': ['tableid', 'featureid'],
        'sys_table_label': ['tableid', 'labelname'],
        'sys_table_link': ['tableid', 'tablelinkid'],
        'sys_table_sublabel': ['tableid', 'sublabelname'],
        'sys_user_permission': ['userid', 'permissionid'],
        'sys_user_table_search_field': ['userid', 'tableid', 'fieldid'],
    }

    # Disattiviamo i controlli per le chiavi esterne durante l'operazione
    cursor.execute("SET FOREIGN_KEY_CHECKS=0;")

    for table, columns in tables_to_fix.items():
        # Query per contare quante colonne compongono la PRIMARY KEY attuale
        check_sql = f"""
            SELECT COUNT(*) 
            FROM information_schema.STATISTICS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = '{table}' 
            AND INDEX_NAME = 'PRIMARY';
        """
        cursor.execute(check_sql)
        pk_count = cursor.fetchone()[0]

        # Se il conteggio è 1, significa che la chiave è ancora singola (vecchio stato)
        # Se è maggiore di 1, la chiave composta esiste già e saltiamo l'operazione
        if pk_count == 1:
            pk_cols = ", ".join(columns)
            first_col = columns[0]
            
            print(f"Applying composite PK to {table} ({pk_cols})...")
            
            sql_commands = [
                f"ALTER TABLE {table} ADD INDEX temp_idx_auto ({first_col});",
                f"ALTER TABLE {table} DROP PRIMARY KEY, ADD PRIMARY KEY ({pk_cols});",
                f"ALTER TABLE {table} DROP INDEX temp_idx_auto;"
            ]
            
            for cmd in sql_commands:
                cursor.execute(cmd)
        else:
            print(f"Skipping {table}: Composite PK already exists ({pk_count} columns).")

    cursor.execute("SET FOREIGN_KEY_CHECKS=1;")

class Migration(migrations.Migration):

    dependencies = [
        ('commonapp', '0042_create_initial_settings'),
    ]

    operations = [
        migrations.RunPython(fix_composite_pkeys_safe, reverse_code=migrations.RunPython.noop),
    ]