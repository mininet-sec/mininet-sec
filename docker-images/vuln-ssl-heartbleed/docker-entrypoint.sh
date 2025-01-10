#!/bin/bash

make-ssl-cert generate-default-snakeoil --force-overwrite
/usr/sbin/apache2ctl -DFOREGROUND
