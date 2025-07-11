package main

import (
	"context"
	"fmt"
	"log"
	"math/rand"
	"net/http"
	"os"

	"time"
	"encoding/json"
	"sync/atomic"

	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/log/global"
	"go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploggrpc"
	sdklog "go.opentelemetry.io/otel/sdk/log"
	"go.opentelemetry.io/otel/metric"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"

	"go.opentelemetry.io/otel/trace"
	"runtime"
	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/mem"
)

var (
	tracer         trace.Tracer
	meter          metric.Meter
	requestCounter metric.Int64Counter
	requestLatency metric.Float64Histogram
	activeUsers    metric.Int64UpDownCounter
	// Counters for tracking actual requests
	healthRequests int64
	apiRequests    int64
	metricsRequests int64
	errorRequests  int64
)

func initTelemetry() func() {
	ctx := context.Background()

	// Create resource
	res, err := resource.New(ctx,
		resource.WithAttributes(
			attribute.String("service.name", "go-otel-sample-app"),
			attribute.String("service.version", "1.0.0"),
			attribute.String("environment", getEnv("ENVIRONMENT", "development")),
		),
	)
	if err != nil {
		log.Fatal("Failed to create resource:", err)
	}

	// Setup tracing
	traceExporter, err := otlptracegrpc.New(ctx,
		otlptracegrpc.WithEndpoint(getEnv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "localhost:4317")),
		otlptracegrpc.WithInsecure(),
	)
	if err != nil {
		log.Fatal("Failed to create trace exporter:", err)
	}

	tracerProvider := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(traceExporter),
		sdktrace.WithResource(res),
	)
	otel.SetTracerProvider(tracerProvider)

	// Setup metrics
	metricExporter, err := otlpmetricgrpc.New(ctx,
		otlpmetricgrpc.WithEndpoint(getEnv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "localhost:4317")),
		otlpmetricgrpc.WithInsecure(),
	)
	if err != nil {
		log.Fatal("Failed to create metric exporter:", err)
	}

	meterProvider := sdkmetric.NewMeterProvider(
		sdkmetric.WithReader(sdkmetric.NewPeriodicReader(metricExporter)),
		sdkmetric.WithResource(res),
	)
	otel.SetMeterProvider(meterProvider)

	// Setup logs
	logExporter, err := otlploggrpc.New(ctx,
		otlploggrpc.WithEndpoint(getEnv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "localhost:4317")),
		otlploggrpc.WithInsecure(),
	)
	if err != nil {
		log.Fatal("Failed to create log exporter:", err)
	}

	loggerProvider := sdklog.NewLoggerProvider(
		sdklog.WithResource(res),
		sdklog.WithProcessor(sdklog.NewBatchProcessor(logExporter)),
	)
	global.SetLoggerProvider(loggerProvider)

	// Create tracer and meter
	tracer = otel.Tracer("go-otel-sample-app")
	meter = otel.Meter("go-otel-sample-app")

	// Create metrics
	requestCounter, _ = meter.Int64Counter(
		"http_requests_total",
		metric.WithDescription("Total number of HTTP requests"),
	)

	requestLatency, _ = meter.Float64Histogram(
		"http_request_duration_seconds",
		metric.WithDescription("HTTP request latency in seconds"),
	)

	activeUsers, _ = meter.Int64UpDownCounter(
		"active_users",
		metric.WithDescription("Number of active users"),
	)

	return func() {
		tracerProvider.Shutdown(ctx)
		meterProvider.Shutdown(ctx)
		loggerProvider.Shutdown(ctx)
	}
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	ctx, span := tracer.Start(r.Context(), "health_check")
	defer span.End()

	start := time.Now()
	
	// Log the request
	logData, _ := json.Marshal(map[string]interface{}{
		"timestamp": time.Now().Format(time.RFC3339),
		"level": "info",
		"message": "Health check requested",
		"endpoint": "/health",
		"method": r.Method,
		"trace_id": span.SpanContext().TraceID().String(),
	})
	log.Printf("%s", logData)
	

	
	requestCounter.Add(ctx, 1, metric.WithAttributes(
		attribute.String("method", r.Method),
		attribute.String("endpoint", "/health"),
		attribute.String("status", "200"),
	))
	
	// Increment actual counter
	atomic.AddInt64(&healthRequests, 1)

	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, `{"status": "healthy", "timestamp": "%s"}`, time.Now().Format(time.RFC3339))

	duration := time.Since(start).Seconds()
	requestLatency.Record(ctx, duration, metric.WithAttributes(
		attribute.String("method", r.Method),
		attribute.String("endpoint", "/health"),
	))
}

func metricsHandler(w http.ResponseWriter, r *http.Request) {
	ctx, span := tracer.Start(r.Context(), "get_metrics")
	defer span.End()

	start := time.Now()
	
	// Log the metrics request
	logData, _ := json.Marshal(map[string]interface{}{
		"timestamp": time.Now().Format(time.RFC3339),
		"level": "info",
		"message": "Metrics endpoint accessed",
		"endpoint": "/metrics",
		"method": r.Method,
		"trace_id": span.SpanContext().TraceID().String(),
	})
	log.Printf("%s", logData)

	requestCounter.Add(ctx, 1, metric.WithAttributes(
		attribute.String("method", r.Method),
		attribute.String("endpoint", "/metrics"),
		attribute.String("status", "200"),
	))
	
	// Increment actual counter
	atomic.AddInt64(&metricsRequests, 1)

	// Simulate some business metrics
	users := rand.Intn(100) + 50
	activeUsers.Add(ctx, int64(users), metric.WithAttributes(
		attribute.String("region", "us-west-2"),
	))

	// Return Prometheus format metrics with actual counters
	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	
	// Get current counter values
	healthCount := atomic.LoadInt64(&healthRequests)
	apiCount := atomic.LoadInt64(&apiRequests)
	metricsCount := atomic.LoadInt64(&metricsRequests)
	errorCount := atomic.LoadInt64(&errorRequests)
	
	// Get system metrics
	cpuPercent, _ := cpu.Percent(0, false)
	memStats := &runtime.MemStats{}
	runtime.ReadMemStats(memStats)
	vmem, _ := mem.VirtualMemory()
	
	fmt.Fprintf(w, `# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",endpoint="/health",status="200"} %d
http_requests_total{method="GET",endpoint="/api",status="200"} %d
http_requests_total{method="GET",endpoint="/api",status="500"} %d
http_requests_total{method="GET",endpoint="/metrics",status="200"} %d

# HELP active_users Active users
# TYPE active_users gauge
active_users{region="us-west-2"} %d

# HELP go_cpu_usage_percent CPU usage percentage
# TYPE go_cpu_usage_percent gauge
go_cpu_usage_percent{app="go-otel-sample-app"} %.2f

# HELP go_memory_usage_bytes Memory usage in bytes
# TYPE go_memory_usage_bytes gauge
go_memory_usage_bytes{app="go-otel-sample-app"} %d

# HELP go_memory_usage_percent Memory usage percentage
# TYPE go_memory_usage_percent gauge
go_memory_usage_percent{app="go-otel-sample-app"} %.2f
`, healthCount, apiCount, errorCount, metricsCount, users, cpuPercent[0], memStats.Alloc, vmem.UsedPercent)

	duration := time.Since(start).Seconds()
	requestLatency.Record(ctx, duration, metric.WithAttributes(
		attribute.String("method", r.Method),
		attribute.String("endpoint", "/metrics"),
	))
}

func apiHandler(w http.ResponseWriter, r *http.Request) {
	ctx, span := tracer.Start(r.Context(), "api_request")
	defer span.End()

	start := time.Now()
	
	// Log the request
	logData, _ := json.Marshal(map[string]interface{}{
		"timestamp": time.Now().Format(time.RFC3339),
		"level": "info",
		"message": "API request received",
		"endpoint": "/api",
		"method": r.Method,
		"trace_id": span.SpanContext().TraceID().String(),
	})
	log.Printf("%s", logData)

	// Simulate some processing time
	time.Sleep(time.Duration(rand.Intn(100)) * time.Millisecond)

	status := "200"
	if rand.Float32() < 0.1 { // 10% error rate
		status = "500"
		// Log error
		errorData, _ := json.Marshal(map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
			"level": "error",
			"message": "Internal server error occurred",
			"endpoint": "/api",
			"status_code": 500,
			"trace_id": span.SpanContext().TraceID().String(),
		})
		log.Printf("%s", errorData)
		// Increment error counter
		atomic.AddInt64(&errorRequests, 1)
		w.WriteHeader(http.StatusInternalServerError)
		fmt.Fprintf(w, `{"error": "Internal server error"}`)
	} else {
		// Log success
		successData, _ := json.Marshal(map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
			"level": "info",
			"message": "API request processed successfully",
			"endpoint": "/api",
			"status_code": 200,
			"trace_id": span.SpanContext().TraceID().String(),
		})
		log.Printf("%s", successData)
		// Increment API counter
		atomic.AddInt64(&apiRequests, 1)
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintf(w, `{
			"message": "Hello from Go OTEL app!",
			"request_id": "%s",
			"timestamp": "%s"
		}`, span.SpanContext().TraceID().String(), time.Now().Format(time.RFC3339))
	}

	requestCounter.Add(ctx, 1, metric.WithAttributes(
		attribute.String("method", r.Method),
		attribute.String("endpoint", "/api"),
		attribute.String("status", status),
	))

	duration := time.Since(start).Seconds()
	requestLatency.Record(ctx, duration, metric.WithAttributes(
		attribute.String("method", r.Method),
		attribute.String("endpoint", "/api"),
	))
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// Background log generator
func generateBackgroundLogs() {
	for {
		time.Sleep(time.Duration(rand.Intn(10)+5) * time.Second)
		
		logTypes := []string{"info", "warning", "error"}
		messages := []string{
			"Background task completed",
			"Database connection pool status check",
			"Cache cleanup operation",
			"Memory usage within normal range",
			"High CPU usage detected",
			"Slow query detected",
			"Connection timeout occurred",
		}
		
		logType := logTypes[rand.Intn(len(logTypes))]
		message := messages[rand.Intn(len(messages))]
		
		logData, _ := json.Marshal(map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
			"level": logType,
			"message": message,
			"service": "go-otel-sample-app",
			"background_task": true,
		})
		log.Printf("%s", logData)
	}
}

func main() {
	shutdown := initTelemetry()
	defer shutdown()
	
	// Start background log generation
	go generateBackgroundLogs()

	mux := http.NewServeMux()
	mux.HandleFunc("/health", healthHandler)
	mux.HandleFunc("/metrics", metricsHandler)
	mux.HandleFunc("/api", apiHandler)

	// Wrap with OTEL HTTP instrumentation
	handler := otelhttp.NewHandler(mux, "go-otel-sample-app")

	port := getEnv("PORT", "8080")
	
	// Log application startup
	startupData, _ := json.Marshal(map[string]interface{}{
		"timestamp": time.Now().Format(time.RFC3339),
		"level": "info",
		"message": "Go OTEL sample app starting",
		"port": port,
		"service": "go-otel-sample-app",
		"version": "1.0.0",
	})
	log.Printf("%s", startupData)
	
	if err := http.ListenAndServe(":"+port, handler); err != nil {
		log.Fatal("Server failed to start:", err)
	}
}