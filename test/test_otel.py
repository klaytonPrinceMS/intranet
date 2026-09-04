"""Test script for OTel LGTM stack integration.

Script de teste para verificar se a stack OTel LGTM está funcionando.

Usage:
    python test/test_otel.py

Author: Klayton Prince
Date: 2026-09-04
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mod_intranet.docker_detector import (
    docker_disponivel,
    docker_compose_disponivel,
    otel_stack_rodando,
    status_otel_stack,
    get_otel_info,
    print_otel_info
)


def test_docker_detection():
    """Test Docker detection."""
    print("=== Teste de Detecção Docker ===")
    
    docker_ok = docker_disponivel()
    print(f"Docker disponível: {docker_ok}")
    
    compose_ok = docker_compose_disponivel()
    print(f"Docker Compose disponível: {compose_ok}")
    
    return docker_ok and compose_ok


def test_otel_stack():
    """Test OTel stack status."""
    print("\n=== Teste da Stack OTel ===")
    
    if not docker_disponivel():
        print("Docker não disponível. Pulando teste da stack.")
        return False
    
    stack_ok = otel_stack_rodando()
    print(f"Stack OTel rodando: {stack_ok}")
    
    if stack_ok:
        status = status_otel_stack()
        print("Status dos serviços:")
        for service, info in status.items():
            state = info.get('state', 'unknown')
            print(f"  {service}: {state}")
    
    return stack_ok


def test_otel_info():
    """Test OTel info display."""
    print("\n=== Teste de Informações OTel ===")
    print_otel_info()
    return True


def test_otel_import():
    """Test OTel integration import."""
    print("\n=== Teste de Import OTel ===")
    
    try:
        from mod_intranet.otel_integracao import (
            inicializar_otel,
            get_tracer,
            criar_span,
            get_meter,
            criar_contador,
            obter_info_otel
        )
        print("✓ Módulo otel_integracao importado com sucesso")
        
        info = obter_info_otel()
        print(f"✓ OTel disponível: {info['available']}")
        print(f"✓ Docker disponível: {info['docker']}")
        print(f"✓ Stack rodando: {info['stack_running']}")
        
        return True
    except ImportError as e:
        print(f"✗ Erro ao importar otel_integracao: {e}")
        print("  Instale as dependências: pip install opentelemetry-api opentelemetry-sdk")
        return False


def main():
    """Run all tests."""
    print("Iniciando testes de integração OTel...\n")
    
    results = []
    
    # Test 1: Docker detection
    results.append(("Detecção Docker", test_docker_detection()))
    
    # Test 2: OTel stack
    results.append(("Stack OTel", test_otel_stack()))
    
    # Test 3: OTel info
    results.append(("Informações OTel", test_otel_info()))
    
    # Test 4: OTel import
    results.append(("Import OTel", test_otel_import()))
    
    # Summary
    print("\n=== Resumo dos Testes ===")
    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*50)
    if all_passed:
        print("Todos os testes passaram!")
    else:
        print("Alguns testes falharam. Verifique as mensagens acima.")
    print("="*50)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())