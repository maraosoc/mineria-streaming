# Task 5: Infraestructura AWS con Terraform

## Descripción
Este proyecto configura una instancia EC2 en AWS que ejecuta el script `main.py` para procesar datos desde S3 usando Polars.

## Estructura de archivos

```
task_5/
├── main.py                    # Script principal de procesamiento con Polars
├── run.sh                     # Script para ejecutar todo el flujo
└── infrastructure/
    ├── backend.tf             # Configuración del backend de Terraform (S3)
    ├── main.tf                # Recursos de AWS (EC2, IAM, Security Groups)
    ├── variables.tf           # Variables de Terraform
    └── user_data.sh           # Script de inicialización de EC2
```

## Flujo de ejecución

1. **Preparación (run.sh)**:
   - Sube `main.py` a S3: `s3://BUCKET/scripts/EXPERIMENT/main.py`
   - Los datos ya deben estar en: `s3://BUCKET/data/`

2. **Terraform apply**:
   - Crea instancia EC2 con Ubuntu
   - Configura IAM role con permisos S3
   - Ejecuta `user_data.sh` al iniciar

3. **Ejecución en EC2 (user_data.sh)**:
   - Instala Python 3 y dependencias (pandas, polars)
   - Descarga script desde S3: `main.py`
   - Descarga datos desde S3: `data/*.json`
   - Ejecuta: `python3 main.py --input /home/ubuntu/EXPERIMENT/data`
   - Sube resultados a S3: `s3://BUCKET/results/EXPERIMENT/output.log`

4. **Post-procesamiento (run.sh)**:
   - Espera hasta 5 minutos por los resultados
   - Descarga y muestra el output.log
   - Destruye la infraestructura con `terraform destroy`

## Variables importantes

### En run.sh:
- `BUCKET`: Nombre del bucket S3
- `EXPERIMENT`: Nombre del experimento (ej: "polars_streaming")
- `SOURCE`: Ruta S3 de los datos

### En variables.tf:
- `bucket_name`: Bucket S3 para scripts/datos/resultados
- `experiment_name`: Nombre del experimento
- `source_name`: Ruta S3 de origen
- `instance_type`: Tipo de instancia EC2 (default: m5.2xlarge)
- `region`: Región AWS (default: us-east-2)
- `profile`: Perfil AWS CLI (default: maraosoc)

## Requisitos previos

1. **AWS CLI configurado** con perfil "maraosoc"
2. **Terraform instalado**
3. **Bucket S3 creado**: `mineria-benchmark-maraosoc-data`
4. **Backend S3 para Terraform**: `mineria-benchmark-maraosoc-terraform-state`
5. **KMS Key**: Para encriptar el estado de Terraform
6. **Datos en S3**: Los archivos JSON deben estar en `s3://BUCKET/data/`

## Uso

### Ejecución completa:
```bash
cd src/task_5
bash run.sh
```

### Ejecución manual paso a paso:

1. Subir script a S3:
```bash
aws s3 cp main.py s3://mineria-benchmark-maraosoc-data/scripts/polars_streaming/main.py --profile maraosoc
```

2. Aplicar infraestructura:
```bash
cd infrastructure
terraform init -backend-config="key=polars_streaming/backend.tfstate"
terraform apply \
  -var="bucket_name=mineria-benchmark-maraosoc-data" \
  -var="experiment_name=polars_streaming" \
  -var="source_name=s3://mineria-benchmark-maraosoc-data/data/"
```

3. Monitorear ejecución:
```bash
# Ver logs de la instancia EC2 via SSM
aws ssm start-session --target INSTANCE_ID --profile maraosoc

# O esperar por el output.log en S3
aws s3 ls s3://mineria-benchmark-maraosoc-data/results/polars_streaming/
```

4. Destruir infraestructura:
```bash
terraform destroy \
  -var="bucket_name=mineria-benchmark-maraosoc-data" \
  -var="experiment_name=polars_streaming" \
  -var="source_name=s3://mineria-benchmark-maraosoc-data/data/"
```

## Prueba local

Antes de ejecutar en AWS, prueba localmente:

```bash
cd src/task_5
python main.py --input ../../data
```

## Permisos IAM necesarios

La instancia EC2 tiene un role IAM con permisos para:
- `s3:GetObject` - Leer archivos del bucket
- `s3:ListBucket` - Listar contenido del bucket
- `s3:PutObject` - Escribir resultados al bucket
- `AmazonSSMManagedInstanceCore` - Acceso via Session Manager

## Troubleshooting

### Error: "No results found after waiting"
- Verificar que los datos existen en S3
- Revisar logs de CloudWatch de la instancia EC2
- Conectarse via SSM para ver logs: `cat /home/ubuntu/output.log`

### Error: "module 'polars' has no attribute..."
- Verificar versión de Polars instalada
- El código está optimizado para Polars 1.x

### Error: Terraform backend
- Verificar que el bucket de backend existe
- Verificar permisos en el KMS key
- Verificar que el perfil AWS tiene acceso
