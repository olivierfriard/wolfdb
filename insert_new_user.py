
import sys
from werkzeug.security import generate_password_hash, check_password_hash
#import psycopg2
#import psycopg2.extras

email = sys.argv[1]
fn = sys.argv[2].replace("'", "''")
ln = sys.argv[3].replace("'", "''")
institution = sys.argv[4].replace("'", "''")

passwd_sha256 = generate_password_hash(sys.argv[5], method='sha256')

out = ("insert into users (email, firstname, lastname, institution, password) "
 f"VALUES ('{email}', '{fn}', '{ln}', '{institution}', "
 f"'{passwd_sha256}');"
)

print(f"\n{out}\n")