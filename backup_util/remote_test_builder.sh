#!/bin/sh
echo "#!/bin/sh" > remote_test_pass11.sh
cat backup_movs_pass11.log | grep "confirmed duplicate of remote" >> remote_test_pass11.sh
sed -i -e "s/^.*remote server file \[\(.*\)\]\. Can remove.*/echo \"\1\"; open \"\1\"; sleep 7;/" remote_test_pass11.sh 
chmod +x remote_test_pass11.sh
