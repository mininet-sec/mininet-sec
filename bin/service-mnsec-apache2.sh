#!/bin/bash

# TODO: add option to change the port (http/https)

# Default values
AUTH_LOGIN=admin
AUTH_PASS=1q2w3e4r
ACTION=help
ORIG_ARGS=()

NAME=$1
shift

while [[ $# -gt 0 ]]; do
  case $1 in
    --start)
      ACTION=start
      shift
      ;;
    --stop)
      ACTION=stop
      shift
      ;;
    -h|--help)
      ACTION=help
      shift
      ;;
    -l|--login)
      AUTH_LOGIN=$2
      shift
      shift
      ;;
    -p|--pass)
      AUTH_PASS=$2
      shift
      shift
      ;;
    *)
      ORIG_ARGS+=("$1")
      shift # past argument
      ;;
  esac
done

export BASE_DIR=/tmp/mnsec/$NAME/apache2
export APACHE_RUN_USER=www-data
export APACHE_RUN_GROUP=www-data
export APACHE_PID_FILE=$BASE_DIR/apache2.pid
export APACHE_RUN_DIR=$BASE_DIR
export APACHE_LOCK_DIR=$BASE_DIR
export APACHE_LOG_DIR=$BASE_DIR
export LANG=C

if [ "$ACTION" = "help" ]; then
  echo "USAGE: $0 NAME [OPTIONS]"
  echo ""
  echo "  NAME         Name of the instance where this service will run (usually hostname)"
  echo "  --start      Start this service"
  echo "  --stop       Stop this service"
  echo "  -l|--login   Username to be used for login on this service"
  echo "  -p|--pass    Password to be used for login on this service"
  echo "  -h|--help    Show this help message and exit"
  exit 0
elif [ "$ACTION" = "stop" ]; then
  kill $(cat $APACHE_PID_FILE)
  exit 0
fi

rm -rf $BASE_DIR
cp -r /etc/apache2 $BASE_DIR

mkdir $BASE_DIR/www
echo "<h1>Test server at $NAME</h1>" > $BASE_DIR/www/index.html
sed -i "s@DocumentRoot /var/www/html@DocumentRoot $BASE_DIR/www@g" $BASE_DIR/sites-available/*.conf
sed -i "s@Directory /var/www/@Directory $BASE_DIR/www/@g" $BASE_DIR/apache2.conf

# fix eventual permission issues to allow www-data read content
f=$BASE_DIR/www
while [[ $f != / ]]; do chmod o+rx "$f"; f=$(dirname "$f"); done


cat > $BASE_DIR/conf-available/custom-auth.conf <<EOF
<Directory "$BASE_DIR/www/admin">
      AuthType Basic
      AuthName "Restricted Content"
      AuthUserFile $BASE_DIR/htpasswd
      Require valid-user
</Directory>
<Directory "$BASE_DIR/www/auth">
    Options ExecCGI
    SetHandler cgi-script
    Require all granted
</Directory>
EOF
htpasswd -b -c $BASE_DIR/htpasswd $AUTH_LOGIN $AUTH_PASS 2>/dev/null
mkdir $BASE_DIR/www/admin
echo "<h1>Welcome to admin page! (using http basic auth)</h1>" >> $BASE_DIR/www/admin/index.html

mkdir $BASE_DIR/www/auth
cat > $BASE_DIR/www/auth/index.html <<EOF
#!/bin/bash

test -z "\$REQUEST_METHOD" && REQUEST_METHOD=GET

echo "Content-type: text/html"
echo ""

echo "<!DOCTYPE html>
<html lang='en'>
<head>
  <title>HTML Login Form</title>
</head>
<body>"
SHOW_LOGIN=yes
if [ "\$REQUEST_METHOD" = "POST" ]; then
    read QUERY_STRING
    if [ "\$QUERY_STRING" = "username=$AUTH_LOGIN&password=$AUTH_PASS" ]; then
       echo "<h1>Welcome $AUTH_LOGIN! (using html form auth)</h1>"
       SHOW_LOGIN=no
    else
       >&2 echo "Invalid Login attempt for: \$QUERY_STRING"
       echo "  <h3 style='color: red;'>Invalid Login or Password</h3>"
    fi
fi
if [ "\$SHOW_LOGIN" = "yes" ]; then
    echo "  <h1>Enter your login credentials</h1>
  <form action='' method='post'>
    <label for='username'>Username:</label>
    <input type='text' id='username' name='username' placeholder='Enter your Username' required>
    <br/>
    <label for='password'>Password:</label>
    <input type='password' id='password' name='password' placeholder='Enter your Password' required>
    <button type='submit'>Submit</button>
  </form>"
fi
echo "</body>
</html>"
EOF
chmod +x $BASE_DIR/www/auth/index.html

ln -s $BASE_DIR/sites-available/default-ssl.conf $BASE_DIR/sites-enabled/
ln -s $BASE_DIR/mods-available/ssl.load $BASE_DIR/mods-enabled/
ln -s $BASE_DIR/mods-available/ssl.conf $BASE_DIR/mods-enabled/
ln -s $BASE_DIR/mods-available/socache_shmcb.load $BASE_DIR/mods-enabled/
ln -s $BASE_DIR/mods-available/cgi.load $BASE_DIR/mods-enabled/
ln -s $BASE_DIR/conf-available/custom-auth.conf $BASE_DIR/conf-enabled/

set -- "${ORIG_ARGS[@]}"

apache2 -d $BASE_DIR -C 'ServerName 127.0.0.1' $@

sleep 1
