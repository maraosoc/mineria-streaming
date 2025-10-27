#!/bin/bash
# Script de validación de la infraestructura Task 5

echo "=========================================="
echo "Validación de Infraestructura Task 5"
echo "=========================================="
echo

# Variables
BUCKET="mineria-benchmark-maraosoc-data"
EXPERIMENT="polars_streaming"
PROFILE="maraosoc"
REGION="us-east-2"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Contadores
PASSED=0
FAILED=0

check() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $1"
        ((PASSED++))
    else
        echo -e "${RED}✗${NC} $1"
        ((FAILED++))
    fi
}

# 1. Verificar AWS CLI
echo "1. Verificando AWS CLI..."
aws --version > /dev/null 2>&1
check "AWS CLI instalado"

# 2. Verificar perfil AWS
echo
echo "2. Verificando perfil AWS..."
aws configure list --profile $PROFILE > /dev/null 2>&1
check "Perfil '$PROFILE' configurado"

# 3. Verificar acceso a S3
echo
echo "3. Verificando acceso a S3..."
aws s3 ls s3://$BUCKET --profile $PROFILE --region $REGION > /dev/null 2>&1
check "Acceso al bucket '$BUCKET'"

# 4. Verificar que existen datos
echo
echo "4. Verificando datos en S3..."
DATA_COUNT=$(aws s3 ls s3://$BUCKET/data/ --profile $PROFILE --region $REGION 2>/dev/null | wc -l)
if [ $DATA_COUNT -gt 0 ]; then
    echo -e "${GREEN}✓${NC} Encontrados $DATA_COUNT archivos en s3://$BUCKET/data/"
    ((PASSED++))
else
    echo -e "${RED}✗${NC} No se encontraron archivos en s3://$BUCKET/data/"
    ((FAILED++))
fi

# 5. Verificar Terraform
echo
echo "5. Verificando Terraform..."
terraform version > /dev/null 2>&1
check "Terraform instalado"

# 6. Verificar archivos locales
echo
echo "6. Verificando archivos locales..."
[ -f "main.py" ]
check "Archivo main.py existe"

[ -f "infrastructure/main.tf" ]
check "Archivo infrastructure/main.tf existe"

[ -f "infrastructure/variables.tf" ]
check "Archivo infrastructure/variables.tf existe"

[ -f "infrastructure/backend.tf" ]
check "Archivo infrastructure/backend.tf existe"

[ -f "infrastructure/user_data.sh" ]
check "Archivo infrastructure/user_data.sh existe"

[ -f "run.sh" ]
check "Archivo run.sh existe"

# 7. Verificar sintaxis de Terraform
echo
echo "7. Verificando sintaxis de Terraform..."
cd infrastructure
terraform fmt -check > /dev/null 2>&1
check "Formato de Terraform correcto"

terraform validate > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Configuración de Terraform válida"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠${NC} Terraform validate falló (puede requerir init)"
    echo "  Ejecuta: cd infrastructure && terraform init"
fi
cd ..

# 8. Verificar Python y dependencias locales
echo
echo "8. Verificando Python y dependencias..."
python3 --version > /dev/null 2>&1
check "Python 3 instalado"

python3 -c "import polars" > /dev/null 2>&1
check "Polars instalado localmente"

# 9. Verificar que main.py funciona localmente
echo
echo "9. Verificando que main.py funciona..."
python3 main.py --help > /dev/null 2>&1
check "main.py ejecutable"

# 10. Verificar bucket de backend de Terraform
echo
echo "10. Verificando backend de Terraform..."
BACKEND_BUCKET="mineria-benchmark-maraosoc-terraform-state"
aws s3 ls s3://$BACKEND_BUCKET --profile $PROFILE --region $REGION > /dev/null 2>&1
check "Bucket de backend '$BACKEND_BUCKET' accesible"

# Resumen
echo
echo "=========================================="
echo "Resumen de Validación"
echo "=========================================="
echo -e "${GREEN}Pasadas:${NC} $PASSED"
echo -e "${RED}Fallidas:${NC} $FAILED"
echo

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ Todas las validaciones pasaron!${NC}"
    echo "Puedes ejecutar: bash run.sh"
    exit 0
else
    echo -e "${RED}✗ Algunas validaciones fallaron.${NC}"
    echo "Por favor, corrige los errores antes de continuar."
    exit 1
fi
