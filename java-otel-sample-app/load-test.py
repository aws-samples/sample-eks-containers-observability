#!/usr/bin/env python3

import requests
import time
import random
import threading
import sys
from concurrent.futures import ThreadPoolExecutor
import json

class JavaAppLoadTester:
    def __init__(self, base_url="http://localhost:8081", duration=300, users=5):
        self.base_url = base_url
        self.duration = duration
        self.users = users
        self.endpoints = [
            "/health",
            "/api/users", 
            "/api/products",
            "/actuator/prometheus"
        ]
        self.stats = {
            "requests": 0,
            "errors": 0,
            "response_times": []
        }
        self.lock = threading.Lock()
        
    def make_request(self, endpoint):
        """Make a single request and track stats"""
        try:
            start_time = time.time()
            response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
            end_time = time.time()
            
            with self.lock:
                self.stats["requests"] += 1
                self.stats["response_times"].append(end_time - start_time)
                if response.status_code >= 400:
                    self.stats["errors"] += 1
                    
            return response.status_code
        except Exception as e:
            with self.lock:
                self.stats["errors"] += 1
            return 0
    
    def user_simulation(self, user_id):
        """Simulate a single user's behavior"""
        print(f"👤 User {user_id} started")
        end_time = time.time() + self.duration
        
        while time.time() < end_time:
            # Random endpoint selection with weighted probabilities
            weights = [0.3, 0.3, 0.3, 0.1]  # health, users, products, metrics
            endpoint = random.choices(self.endpoints, weights=weights)[0]
            
            self.make_request(endpoint)
            
            # Random delay between requests (0.5-3 seconds)
            time.sleep(random.uniform(0.5, 3.0))
            
            # Occasional burst of requests (10% chance)
            if random.random() < 0.1:
                print(f"💥 User {user_id} generating burst traffic")
                for _ in range(random.randint(3, 8)):
                    burst_endpoint = random.choice(["/api/users", "/api/products"])
                    self.make_request(burst_endpoint)
                    time.sleep(0.1)
        
        print(f"👤 User {user_id} finished")
    
    def monitor_progress(self):
        """Monitor and display progress"""
        start_time = time.time()
        
        while time.time() - start_time < self.duration:
            elapsed = int(time.time() - start_time)
            remaining = self.duration - elapsed
            
            with self.lock:
                total_requests = self.stats["requests"]
                total_errors = self.stats["errors"]
                error_rate = (total_errors / max(total_requests, 1)) * 100
                
                if self.stats["response_times"]:
                    avg_response_time = sum(self.stats["response_times"]) / len(self.stats["response_times"])
                else:
                    avg_response_time = 0
            
            print(f"⏱️  Elapsed: {elapsed}s | Remaining: {remaining}s")
            print(f"📊 Requests: {total_requests} | Errors: {total_errors} ({error_rate:.1f}%) | Avg Response: {avg_response_time:.3f}s")
            
            # Try to get current metrics
            try:
                response = requests.get(f"{self.base_url}/actuator/prometheus", timeout=5)
                if response.status_code == 200:
                    metrics = response.text
                    for line in metrics.split('\n'):
                        if 'http_requests_total{app="java-otel-sample-app"}' in line:
                            print(f"📈 {line.strip()}")
                        elif 'java_cpu_usage_percent{app="java-otel-sample-app"}' in line:
                            print(f"🖥️  {line.strip()}")
                        elif 'java_memory_usage_bytes{app="java-otel-sample-app"}' in line:
                            print(f"💾 {line.strip()}")
            except:
                pass
            
            print("-" * 80)
            time.sleep(10)
    
    def run(self):
        """Run the load test"""
        print("🚀 Starting Java OTEL App Load Test")
        print(f"📊 Configuration: {self.users} users, {self.duration}s duration")
        print(f"🎯 Target: {self.base_url}")
        
        # Check if app is accessible
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code != 200:
                raise Exception("Health check failed")
            print("✅ Java app is accessible")
        except Exception as e:
            print(f"❌ Cannot access Java app: {e}")
            print("Please run: kubectl port-forward svc/java-otel-sample-app 8081:8080 -n default")
            return
        
        print(f"🎬 Starting {self.users} concurrent users...")
        
        # Start monitoring in background
        monitor_thread = threading.Thread(target=self.monitor_progress)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # Start user simulations
        with ThreadPoolExecutor(max_workers=self.users) as executor:
            futures = [executor.submit(self.user_simulation, i+1) for i in range(self.users)]
            
            # Wait for all users to complete
            for future in futures:
                future.result()
        
        # Final stats
        print("\n🎉 Load test completed!")
        print(f"📊 Final Statistics:")
        print(f"   Total Requests: {self.stats['requests']}")
        print(f"   Total Errors: {self.stats['errors']}")
        print(f"   Error Rate: {(self.stats['errors'] / max(self.stats['requests'], 1)) * 100:.2f}%")
        
        if self.stats["response_times"]:
            response_times = sorted(self.stats["response_times"])
            print(f"   Avg Response Time: {sum(response_times) / len(response_times):.3f}s")
            print(f"   P50 Response Time: {response_times[len(response_times)//2]:.3f}s")
            print(f"   P95 Response Time: {response_times[int(len(response_times)*0.95)]:.3f}s")
        
        print("\n🔍 Check Grafana dashboard for visualizations")

if __name__ == "__main__":
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    users = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    tester = JavaAppLoadTester(duration=duration, users=users)
    tester.run()