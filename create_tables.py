from albumlistbot.models import DatabaseError
from albumlistbot.models.mapping import create_mapping_table


if __name__ == '__main__':
    try:
        create_mapping_table()
    except DatabaseError as e:
        print(f'[db]: ERROR - {e}')