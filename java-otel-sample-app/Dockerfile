FROM public.ecr.aws/docker/library/openjdk:26-slim

WORKDIR /app

COPY target/java-otel-sample-app-1.0.jar app.jar

EXPOSE 8080

CMD ["java", "-jar", "app.jar"]