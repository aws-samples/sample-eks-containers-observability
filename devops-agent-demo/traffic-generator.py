#!/usr/bin/env python3
"""
Traffic Generator for EKS Platform Applications
Generates HTTP traffic to test applications and produce metrics for AWS DevOps Agent analysis
"""

import requests
import time
import random
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

class TrafficGenerator:
    def __init__(self, base_url, app_name, duration=300, requests_per_second=10, error_rate=0.1):
        self.base_url = base_url
        self.app_name = app_name
        self.duration = duration
        self.requests_per_second = requests_per_second
        self.error_rate = error_rate
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.start_time = None
        
    def make_request(self, endpoint="/"):
        """Make a single HTTP request"""
        try:
            # Randomly introduce errors based on error_rate
            if random.random() < self.error_rate:
                # Try to hit a non-existent endpoint to generate 404s
                endpoint = "/error-test-endpoint"
            
            response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
            self.total_requests += 1
            
            if response.status_code == 200:
                self.successful_requests += 1
                return True, response.status_code
            else:
                self.failed_requests += 1
                return False, response.status_code
                
        except requests.exceptions.RequestException as e:
            self.failed_requests += 1
            self.total_requests += 1
            return False, str(e)
    
    def generate_traffic(self):
        """Generate traffic for the specified duration"""
        print(f"\n{'='*60}")
        print(f"Starting traffic generation for {self.app_name}")
        print(f"Target: {self.base_url}")
        print(f"Duration: {self.duration} seconds")
        print(f"Rate: {self.requests_per_second} requests/second")
        print(f"Error Rate: {self.error_rate * 100}%")
        print(f"{'='*60}\n")
        
        self.start_time = time.time()
        end_time = self.start_time + self.duration
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            while time.time() < end_time:
                batch_start = time.time()
                
                # Submit requests for this second
                futures = []
                for _ in range(self.requests_per_second):
                    futures.append(executor.submit(self.make_request))
                
                # Wait for all requests in this batch to complete
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        print(f"Request failed with exception: {e}")
                
                # Calculate elapsed time and print stats
                elapsed = time.time() - self.start_time
                remaining = self.duration - elapsed
                
                if self.total_requests % (self.requests_per_second * 10) == 0:
                    self.print_stats(elapsed, remaining)
                
                # Sleep to maintain the desired rate
                batch_duration = time.time() - batch_start
                sleep_time = max(0, 1.0 - batch_duration)
                time.sleep(sleep_time)
        
        self.print_final_stats()
    
    def print_stats(self, elapsed, remaining):
        """Print current statistics"""
        success_rate = (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0
        current_rps = self.total_requests / elapsed if elapsed > 0 else 0
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] "
              f"Elapsed: {elapsed:.0f}s | Remaining: {remaining:.0f}s | "
              f"Total: {self.total_requests} | Success: {self.successful_requests} | "
              f"Failed: {self.failed_requests} | Success Rate: {success_rate:.1f}% | "
              f"RPS: {current_rps:.1f}")
    
    def print_final_stats(self):
        """Print final statistics"""
        total_duration = time.time() - self.start_time
        avg_rps = self.total_requests / total_duration if total_duration > 0 else 0
        success_rate = (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0
        
        print(f"\n{'='*60}")
        print(f"Traffic Generation Complete for {self.app_name}")
        print(f"{'='*60}")
        print(f"Total Duration: {total_duration:.2f} seconds")
        print(f"Total Requests: {self.total_requests}")
        print(f"Successful Requests: {self.successful_requests}")
        print(f"Failed Requests: {self.failed_requests}")
        print(f"Success Rate: {success_rate:.2f}%")
        print(f"Average RPS: {avg_rps:.2f}")
        print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Generate HTTP traffic to EKS platform applications',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate traffic to sample-metrics-app for 5 minutes at 20 RPS
  python traffic-generator.py --app sample-metrics --duration 300 --rps 20
  
  # Generate traffic to all apps simultaneously
  python traffic-generator.py --app all --duration 600 --rps 15
  
  # Generate traffic with custom error rate
  python traffic-generator.py --app go-otel --duration 300 --rps 10 --error-rate 0.2
        """
    )
    
    parser.add_argument('--app', 
                        choices=['sample-metrics', 'otel', 'go-otel', 'java-otel', 'all'],
                        default='all',
                        help='Application to target (default: all)')
    
    parser.add_argument('--duration', 
                        type=int, 
                        default=300,
                        help='Duration in seconds (default: 300)')
    
    parser.add_argument('--rps', 
                        type=int, 
                        default=10,
                        help='Requests per second (default: 10)')
    
    parser.add_argument('--error-rate', 
                        type=float, 
                        default=0.1,
                        help='Error rate as decimal (default: 0.1 = 10%%)')
    
    parser.add_argument('--base-url',
                        type=str,
                        help='Override base URL (for port-forwarded services)')
    
    args = parser.parse_args()
    
    # Define application endpoints
    apps = {
        'sample-metrics': {
            'name': 'Sample Metrics App',
            'url': args.base_url or 'http://localhost:8000',
            'port': 8000
        },
        'otel': {
            'name': 'Python OTEL App',
            'url': args.base_url or 'http://localhost:8080',
            'port': 8080
        },
        'go-otel': {
            'name': 'Go OTEL App',
            'url': args.base_url or 'http://localhost:8090',
            'port': 8090
        },
        'java-otel': {
            'name': 'Java OTEL App',
            'url': args.base_url or 'http://localhost:8081',
            'port': 8081
        }
    }
    
    # Determine which apps to target
    if args.app == 'all':
        target_apps = list(apps.keys())
    else:
        target_apps = [args.app]
    
    print("\n" + "="*60)
    print("EKS Platform Traffic Generator")
    print("="*60)
    print(f"Target Applications: {', '.join([apps[app]['name'] for app in target_apps])}")
    print(f"Duration: {args.duration} seconds")
    print(f"Rate: {args.rps} requests/second per app")
    print(f"Error Rate: {args.error_rate * 100}%")
    print("="*60)
    
    # Check if services are accessible
    print("\nChecking service availability...")
    accessible_apps = []
    for app_key in target_apps:
        app = apps[app_key]
        try:
            response = requests.get(app['url'], timeout=2)
            print(f"✓ {app['name']} is accessible at {app['url']}")
            accessible_apps.append(app_key)
        except requests.exceptions.RequestException as e:
            print(f"✗ {app['name']} is NOT accessible at {app['url']}")
            print(f"  Error: {e}")
            print(f"  Hint: Run 'kubectl port-forward svc/{app_key.replace('otel', 'otel-sample-app').replace('sample-metrics', 'sample-metrics-app')} {app['port']}:{app['port']} -n default'")
    
    if not accessible_apps:
        print("\n❌ No applications are accessible. Please set up port forwarding first.")
        print("\nExample commands:")
        print("  kubectl port-forward svc/sample-metrics-app 8000:8000 -n default &")
        print("  kubectl port-forward svc/otel-sample-app 8080:8000 -n default &")
        print("  kubectl port-forward svc/go-otel-sample-app 8090:8080 -n default &")
        print("  kubectl port-forward svc/java-otel-sample-app 8081:8080 -n default &")
        sys.exit(1)
    
    # Generate traffic
    print(f"\nStarting traffic generation to {len(accessible_apps)} application(s)...\n")
    
    if len(accessible_apps) == 1:
        # Single app - run synchronously
        app_key = accessible_apps[0]
        app = apps[app_key]
        generator = TrafficGenerator(
            base_url=app['url'],
            app_name=app['name'],
            duration=args.duration,
            requests_per_second=args.rps,
            error_rate=args.error_rate
        )
        generator.generate_traffic()
    else:
        # Multiple apps - run in parallel
        with ThreadPoolExecutor(max_workers=len(accessible_apps)) as executor:
            futures = []
            for app_key in accessible_apps:
                app = apps[app_key]
                generator = TrafficGenerator(
                    base_url=app['url'],
                    app_name=app['name'],
                    duration=args.duration,
                    requests_per_second=args.rps,
                    error_rate=args.error_rate
                )
                futures.append(executor.submit(generator.generate_traffic))
            
            # Wait for all generators to complete
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"Generator failed with exception: {e}")
    
    print("\n✅ Traffic generation completed for all applications!")
    print("\nNext steps:")
    print("1. Check metrics in Prometheus: kubectl port-forward svc/prometheus-service 9090:9090 -n monitoring")
    print("2. View Grafana dashboards for application metrics")
    print("3. Use AWS DevOps Agent to analyze the generated metrics and logs")


if __name__ == '__main__':
    main()
