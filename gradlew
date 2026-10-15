#!/bin/sh
# Gradle start-up script for POSIX generated from the standard Gradle wrapper.
# The companion gradle-wrapper.jar is checked in under gradle/wrapper.
APP_HOME=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P) || exit
CLASSPATH=$APP_HOME/gradle/wrapper/gradle-wrapper.jar
if [ ! -f "$CLASSPATH" ]; then
  echo "ERROR: Gradle wrapper JAR is missing: $CLASSPATH" >&2
  exit 1
fi
exec java -Xmx64m -Xms64m $JAVA_OPTS $GRADLE_OPTS "-Dorg.gradle.appname=$(basename "$0")" -classpath "$CLASSPATH" org.gradle.wrapper.GradleWrapperMain "$@"
