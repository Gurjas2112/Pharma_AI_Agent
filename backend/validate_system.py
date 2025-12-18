"""
PharmaAI System Validation Script
Verifies all components are properly configured
"""

import os
import sys

def check_file_exists(path, description):
    """Check if a file exists and print status"""
    exists = os.path.exists(path)
    status = "✓" if exists else "✗"
    print(f"{status} {description}: {path}")
    return exists

def check_directory_exists(path, description):
    """Check if a directory exists and print status"""
    exists = os.path.isdir(path)
    status = "✓" if exists else "✗"
    print(f"{status} {description}: {path}")
    return exists

def check_import(module_name, package_name=None):
    """Check if a Python module can be imported"""
    try:
        __import__(module_name)
        print(f"✓ {package_name or module_name} is installed")
        return True
    except ImportError:
        print(f"✗ {package_name or module_name} is NOT installed")
        return False

def main():
    print("=" * 60)
    print("PharmaAI System Validation")
    print("=" * 60)
    
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    all_checks_passed = True
    
    # Check core files
    print("\n📁 Core Files:")
    all_checks_passed &= check_file_exists(
        os.path.join(base_path, "backend", "agents", "master_agent.py"),
        "Master Agent"
    )
    all_checks_passed &= check_file_exists(
        os.path.join(base_path, "backend", "agents", "report_agent.py"),
        "Report Agent"
    )
    all_checks_passed &= check_file_exists(
        os.path.join(base_path, "backend", "agents", "visualization_service.py"),
        "Visualization Service"
    )
    
    # Check logo
    print("\n🎨 Assets:")
    all_checks_passed &= check_file_exists(
        os.path.join(base_path, "App_logo.png"),
        "App Logo"
    )
    
    # Check directories
    print("\n📂 Directories:")
    all_checks_passed &= check_directory_exists(
        os.path.join(base_path, "backend", "reports"),
        "Reports Directory"
    )
    all_checks_passed &= check_directory_exists(
        os.path.join(base_path, "backend", "reports", "charts"),
        "Charts Directory"
    )
    
    # Check Python dependencies
    print("\n📦 Python Dependencies:")
    all_checks_passed &= check_import("matplotlib")
    all_checks_passed &= check_import("reportlab")
    all_checks_passed &= check_import("PIL", "Pillow")
    all_checks_passed &= check_import("fastapi")
    all_checks_passed &= check_import("uvicorn")
    
    # Verify key methods exist
    print("\n🔧 Code Validation:")
    try:
        sys.path.insert(0, os.path.join(base_path, "backend"))
        from agents.visualization_service import VisualizationService
        from agents.report_agent import ReportGeneratorAgent
        
        viz = VisualizationService()
        required_methods = [
            'generate_market_size_chart',
            'generate_patent_expiry_histogram',
            'generate_clinical_phase_pie',
            'generate_import_dependency_heatmap',
            'generate_all_charts'
        ]
        
        for method in required_methods:
            if hasattr(viz, method):
                print(f"✓ VisualizationService.{method}() exists")
            else:
                print(f"✗ VisualizationService.{method}() NOT FOUND")
                all_checks_passed = False
        
        report = ReportGeneratorAgent()
        if hasattr(report, '_convert_with_reportlab_professional'):
            print(f"✓ ReportGeneratorAgent._convert_with_reportlab_professional() exists")
        else:
            print(f"✗ ReportGeneratorAgent._convert_with_reportlab_professional() NOT FOUND")
            all_checks_passed = False
            
    except Exception as e:
        print(f"✗ Error importing modules: {e}")
        all_checks_passed = False
    
    # Final verdict
    print("\n" + "=" * 60)
    if all_checks_passed:
        print("✅ ALL CHECKS PASSED - System is ready for testing!")
        print("\nNext steps:")
        print("1. Start backend: cd backend && uvicorn main:app --reload")
        print("2. Open frontend: http://localhost:3000")
        print("3. Test query: 'Evaluate Montelukast for cancer repurposing'")
    else:
        print("❌ SOME CHECKS FAILED - Please review errors above")
        print("\nCommon fixes:")
        print("- Install missing packages: pip install matplotlib reportlab pillow")
        print("- Create missing directories: mkdir -p backend/reports/charts")
        print("- Verify logo file exists at root: App_logo.png")
    print("=" * 60)
    
    return 0 if all_checks_passed else 1

if __name__ == "__main__":
    sys.exit(main())
