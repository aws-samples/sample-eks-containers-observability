FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

COPY target/java-otel-sample-app-1.0.jar app.jar

EXPOSE 8080

CMD ["java", "-jar", "app.jar"]