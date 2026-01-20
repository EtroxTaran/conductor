# Multi-stage build for Spring Boot
# Optimized for production with ARM64 support

# Build stage
FROM eclipse-temurin:21-jdk AS builder

WORKDIR /app

# Copy gradle files
COPY gradle gradle
COPY gradlew build.gradle.kts settings.gradle.kts ./

# Download dependencies
RUN ./gradlew dependencies --no-daemon

# Copy source
COPY src src

# Build
RUN ./gradlew bootJar --no-daemon

# Production stage
FROM eclipse-temurin:21-jre-alpine AS production

WORKDIR /app

# Create non-root user
RUN addgroup --system --gid 1001 spring && \
    adduser --system --uid 1001 spring

# Copy the built jar
COPY --from=builder /app/build/libs/*.jar app.jar

# Set ownership
RUN chown -R spring:spring /app

USER spring

EXPOSE 8080

ENV JAVA_OPTS="-Xms256m -Xmx512m"

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
