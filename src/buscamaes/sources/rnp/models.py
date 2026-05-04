from dataclasses import dataclass


@dataclass
class VehicleResult:
    placa: str = ""
    categoria: str = ""
    marca: str = ""
    estilo: str = ""
    año_fabricacion: str = ""
    cilindrada_cc: str = ""
    valor_contrato: str = ""
    propietario_id: str = ""
    propietario_nombre: str = ""
