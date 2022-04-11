#!/usr/bin/env bash

if [ $# -ne 2 ]; then echo "Working directory (.tox dir) required as first arg, scanner version as second"; fi

WORKDIR=$1
SONAR_SCANNER_VER=$2
SONAR_SCANNER_URL="https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-${SONAR_SCANNER_VER}-linux.zip"

# Fetch scanner
wget -O "$WORKDIR/sonarqube/scanner.zip" "$SONAR_SCANNER_URL"

# Unpack scanner to .tox working dir
unzip "$WORKDIR/sonarqube/scanner.zip" -d "$WORKDIR/sonarqube"

# Inject URI for sonarqube host to config file
echo "sonar.host.url=***REMOVED***" >> "${WORKDIR}/sonarqube/sonar-scanner-${SONAR_SCANNER_VER}-linux/conf/sonar-scanner.properties"

# Add trust certs for redhat internal websites to keystore
wget ***REMOVED*** -O "${WORKDIR}/sonarqube/sonar-scanner-${SONAR_SCANNER_VER}-linux/jre/lib/security/Red_Hat_IT_Root_CA.crt" --no-check-certificate
wget ***REMOVED*** -O "${WORKDIR}/sonarqube/sonar-scanner-${SONAR_SCANNER_VER}-linux/jre/lib/security/PKI_CA_Chain.crt" --no-check-certificate
keytool -import -trustcacerts -noprompt -storepass changeit -alias rhitrootca -file "${WORKDIR}/sonarqube/sonar-scanner-${SONAR_SCANNER_VER}-linux/jre/lib/security/Red_Hat_IT_Root_CA.crt" -keystore "${WORKDIR}/sonarqube/sonar-scanner-${SONAR_SCANNER_VER}-linux/jre/lib/security/cacerts"
keytool -import -trustcacerts -noprompt -storepass changeit -alias pkicachain -file "${WORKDIR}/sonarqube/sonar-scanner-${SONAR_SCANNER_VER}-linux/jre/lib/security/PKI_CA_Chain.crt" -keystore "${WORKDIR}/sonarqube/sonar-scanner-${SONAR_SCANNER_VER}-linux/jre/lib/security/cacerts"

# Done!