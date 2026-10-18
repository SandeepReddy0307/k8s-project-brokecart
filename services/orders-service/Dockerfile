FROM maven:3.9.11-eclipse-temurin-17 AS build
WORKDIR /workspace
COPY pom.xml ./
COPY libraries ./libraries
COPY services ./services
RUN --mount=type=cache,target=/root/.m2 mvn -B package -DskipTests
FROM eclipse-temurin:17-jre-alpine
RUN addgroup -g 10001 app && adduser -D -u 10001 -G app app
WORKDIR /app
COPY --from=build --chown=10001:10001 /workspace/services/orders-service/target/orders-service-0.1.0-SNAPSHOT.jar /app/app.jar
USER 10001:10001
ENV PORT=8080 JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=65 -XX:+ExitOnOutOfMemoryError"
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
