#!/bin/bash
# Interactive deployment script for EKS Platform with menu-based selection

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_color() {
    color=$1
    message=$2
    echo -e "${color}${message}${NC}"
}

# Function to print header
print_header() {
    echo ""
    print_color "$BLUE" "=============================================="
    print_color "$BLUE" "$1"
    print_color "$BLUE" "=============================================="
    echo ""
}

# Function to print menu
print_menu() {
    print_header "EKS Platform Deployment Configuration"
    
    echo "Select deployment options:"
    echo ""
    echo "1. Compute Mode:"
    echo "   a) Auto Mode (EKS Auto Mode - recommended)"
    echo "   b) Fargate (EKS Fargate)"
    echo ""
    echo "2. DevOps Agent:"
    echo "   a) Enabled (deploy with DevOps Agent integration)"
    echo "   b) Disabled (skip DevOps Agent)"
    echo ""
    echo "3. Quick Deploy Options:"
    echo "   1) Deploy with Auto Mode only"
    echo "   2) Deploy with Auto Mode + DevOps Agent"
    echo "   3) Deploy with Fargate only"
    echo "   4) Deploy with Fargate + DevOps Agent"
    echo "   5) Custom configuration"
    echo "   6) Show CDK diff"
    echo "   7) Destroy all stacks"
    echo "   8) Exit"
    echo ""
}

# Function to deploy with options
deploy_with_options() {
    compute_mode=$1
    devops_agent=$2
    
    print_header "Deploying EKS Platform"
    print_color "$GREEN" "Configuration:"
    print_color "$GREEN" "  - Compute Mode: $compute_mode"
    print_color "$GREEN" "  - DevOps Agent: $devops_agent"
    echo ""
    
    # Build CDK command
    cdk_cmd="cdk deploy --all"
    
    if [ "$compute_mode" != "auto-mode" ]; then
        cdk_cmd="$cdk_cmd -c compute_mode=$compute_mode"
    fi
    
    if [ "$devops_agent" == "true" ]; then
        cdk_cmd="$cdk_cmd -c deploy_devops_agent=true"
    fi
    
    print_color "$YELLOW" "Executing: $cdk_cmd"
    echo ""
    
    # Execute deployment
    eval $cdk_cmd
    
    if [ $? -eq 0 ]; then
        print_header "Deployment Successful!"
        
        if [ "$devops_agent" == "true" ]; then
            print_color "$GREEN" "DevOps Agent Stack Deployed!"
            echo ""
            print_color "$YELLOW" "Next Steps:"
            echo "1. Get the DevOps Agent Role ARN:"
            echo "   aws cloudformation describe-stacks --stack-name DevOpsAgentStack \\"
            echo "     --query 'Stacks[0].Outputs[?OutputKey==\`DevOpsAgentRoleArn\`].OutputValue' \\"
            echo "     --output text"
            echo ""
            echo "2. Create Agent Space in AWS Console:"
            echo "   - Navigate to AWS DevOps Agent console"
            echo "   - Click 'Create Agent Space'"
            echo "   - Use the Role ARN from step 1"
            echo ""
            echo "3. Start investigating your EKS cluster!"
            echo ""
        fi
        
        print_color "$GREEN" "View stack outputs:"
        echo "  aws cloudformation describe-stacks --stack-name EKS-Platform-Cluster --query 'Stacks[0].Outputs'"
        echo ""
    else
        print_color "$RED" "Deployment failed. Check the error messages above."
        exit 1
    fi
}

# Function to show diff
show_diff() {
    compute_mode=$1
    devops_agent=$2
    
    print_header "CDK Diff"
    
    cdk_cmd="cdk diff"
    
    if [ "$compute_mode" != "auto-mode" ]; then
        cdk_cmd="$cdk_cmd -c compute_mode=$compute_mode"
    fi
    
    if [ "$devops_agent" == "true" ]; then
        cdk_cmd="$cdk_cmd -c deploy_devops_agent=true"
    fi
    
    eval $cdk_cmd
}

# Function to destroy stacks
destroy_stacks() {
    print_header "Destroy All Stacks"
    print_color "$RED" "WARNING: This will destroy all deployed resources!"
    echo ""
    read -p "Are you sure you want to continue? (yes/no): " confirm
    
    if [ "$confirm" == "yes" ]; then
        print_color "$YELLOW" "Destroying all stacks..."
        cdk destroy --all
        
        if [ $? -eq 0 ]; then
            print_color "$GREEN" "All stacks destroyed successfully!"
        else
            print_color "$RED" "Destroy failed. Check the error messages above."
        fi
    else
        print_color "$YELLOW" "Destroy cancelled."
    fi
}

# Function for custom configuration
custom_config() {
    print_header "Custom Configuration"
    
    echo "Select compute mode:"
    echo "  1) Auto Mode"
    echo "  2) Fargate"
    read -p "Enter choice (1-2): " compute_choice
    
    case $compute_choice in
        1) compute_mode="auto-mode" ;;
        2) compute_mode="fargate" ;;
        *) 
            print_color "$RED" "Invalid choice. Using Auto Mode."
            compute_mode="auto-mode"
            ;;
    esac
    
    echo ""
    read -p "Deploy DevOps Agent? (y/n): " devops_choice
    
    case $devops_choice in
        y|Y) devops_agent="true" ;;
        *) devops_agent="false" ;;
    esac
    
    echo ""
    read -p "Show diff before deploying? (y/n): " diff_choice
    
    if [ "$diff_choice" == "y" ] || [ "$diff_choice" == "Y" ]; then
        show_diff "$compute_mode" "$devops_agent"
        echo ""
        read -p "Proceed with deployment? (y/n): " proceed
        if [ "$proceed" != "y" ] && [ "$proceed" != "Y" ]; then
            print_color "$YELLOW" "Deployment cancelled."
            return
        fi
    fi
    
    deploy_with_options "$compute_mode" "$devops_agent"
}

# Main menu loop
main() {
    # Check if CDK is installed
    if ! command -v cdk &> /dev/null; then
        print_color "$RED" "Error: AWS CDK is not installed."
        echo "Install it with: npm install -g aws-cdk"
        exit 1
    fi
    
    # Check if Python dependencies are installed
    if ! python -c "import aws_cdk" &> /dev/null; then
        print_color "$RED" "Error: Python dependencies not installed."
        echo "Install them with: pip install -r requirements.txt"
        exit 1
    fi
    
    while true; do
        print_menu
        read -p "Enter your choice (1-8): " choice
        
        case $choice in
            1)
                deploy_with_options "auto-mode" "false"
                ;;
            2)
                deploy_with_options "auto-mode" "true"
                ;;
            3)
                deploy_with_options "fargate" "false"
                ;;
            4)
                deploy_with_options "fargate" "true"
                ;;
            5)
                custom_config
                ;;
            6)
                echo ""
                read -p "Compute mode (auto-mode/fargate) [auto-mode]: " compute_mode
                compute_mode=${compute_mode:-auto-mode}
                read -p "Include DevOps Agent? (y/n) [n]: " devops_choice
                devops_agent="false"
                if [ "$devops_choice" == "y" ] || [ "$devops_choice" == "Y" ]; then
                    devops_agent="true"
                fi
                show_diff "$compute_mode" "$devops_agent"
                ;;
            7)
                destroy_stacks
                ;;
            8)
                print_color "$GREEN" "Exiting. Goodbye!"
                exit 0
                ;;
            *)
                print_color "$RED" "Invalid choice. Please try again."
                ;;
        esac
        
        echo ""
        read -p "Press Enter to continue..."
    done
}

# Run main function
main
