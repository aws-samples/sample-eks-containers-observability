package com.example.app.controller;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.lang.management.ManagementFactory;
import java.lang.management.MemoryMXBean;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.Random;

@RestController
public class ApiController {

    private static final Logger logger = LoggerFactory.getLogger(ApiController.class);
    private final Random random = new Random();
    
    private final Counter httpRequestsTotal;
    private final Timer httpRequestDuration;

    public ApiController(MeterRegistry meterRegistry) {
        this.httpRequestsTotal = Counter.builder("http_requests_total")
                .description("Total HTTP requests")
                .tag("app", "java-otel-sample-app")
                .register(meterRegistry);
                
        this.httpRequestDuration = Timer.builder("http_request_duration_seconds")
                .description("HTTP request duration")
                .tag("app", "java-otel-sample-app")
                .register(meterRegistry);
                
        Gauge.builder("java_cpu_usage_percent", this, ApiController::getCpuUsage)
                .description("CPU usage percentage")
                .tag("app", "java-otel-sample-app")
                .register(meterRegistry);
                
        Gauge.builder("java_memory_usage_bytes", this, ApiController::getMemoryUsage)
                .description("Memory usage in bytes")
                .tag("app", "java-otel-sample-app")
                .register(meterRegistry);
    }

    @GetMapping("/health")
    public Map<String, Object> health() {
        Timer.Sample sample = Timer.start();
        
        try {
            httpRequestsTotal.increment();
            
            Map<String, Object> response = new HashMap<>();
            response.put("status", "healthy");
            response.put("timestamp", Instant.now().toString());
            response.put("service", "java-otel-sample-app");
            
            logger.info("Health check requested - service: java-otel-sample-app, status: healthy");
            
            return response;
        } finally {
            sample.stop(httpRequestDuration);
        }
    }

    @GetMapping("/api/users")
    public Map<String, Object> getUsers() {
        Timer.Sample sample = Timer.start();
        
        try {
            Thread.sleep(random.nextInt(100));
            
            if (random.nextDouble() < 0.1) {
                httpRequestsTotal.increment();
                logger.error("Internal server error occurred - endpoint: /api/users, service: java-otel-sample-app, error_type: simulated_error");
                throw new RuntimeException("Internal server error");
            }
            
            httpRequestsTotal.increment();
            
            Map<String, Object> response = new HashMap<>();
            response.put("users", new String[]{"user1", "user2", "user3"});
            response.put("count", 3);
            response.put("timestamp", Instant.now().toString());
            
            logger.info("Users endpoint accessed - service: java-otel-sample-app, endpoint: /api/users, method: GET, response_count: {}", response.get("count"));
            
            return response;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException(e);
        } finally {
            sample.stop(httpRequestDuration);
        }
    }

    @GetMapping("/api/products")
    public Map<String, Object> getProducts() {
        Timer.Sample sample = Timer.start();
        
        try {
            Thread.sleep(random.nextInt(150));
            
            if (random.nextDouble() < 0.05) {
                httpRequestsTotal.increment();
                logger.error("Product service error - endpoint: /api/products, service: java-otel-sample-app, error_type: service_unavailable");
                throw new RuntimeException("Product service unavailable");
            }
            
            httpRequestsTotal.increment();
            
            Map<String, Object> response = new HashMap<>();
            response.put("products", new String[]{"product1", "product2", "product3"});
            response.put("count", 3);
            response.put("timestamp", Instant.now().toString());
            
            logger.info("Products endpoint accessed - service: java-otel-sample-app, endpoint: /api/products, method: GET, response_count: {}", response.get("count"));
            
            return response;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException(e);
        } finally {
            sample.stop(httpRequestDuration);
        }
    }

    private double getCpuUsage() {
        try {
            com.sun.management.OperatingSystemMXBean osBean = 
                (com.sun.management.OperatingSystemMXBean) ManagementFactory.getOperatingSystemMXBean();
            double cpuLoad = osBean.getProcessCpuLoad();
            return cpuLoad >= 0 ? cpuLoad * 100 : 0.0;
        } catch (Exception e) {
            logger.warn("Failed to get CPU usage: {}", e.getMessage());
            return 0.0;
        }
    }

    private double getMemoryUsage() {
        try {
            MemoryMXBean memoryBean = ManagementFactory.getMemoryMXBean();
            return memoryBean.getHeapMemoryUsage().getUsed();
        } catch (Exception e) {
            logger.warn("Failed to get memory usage: {}", e.getMessage());
            return 0.0;
        }
    }
}