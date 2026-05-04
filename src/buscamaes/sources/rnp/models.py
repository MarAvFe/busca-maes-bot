from dataclasses import dataclass


@dataclass
class VehicleResult:
    placa: str = ""
    categoria: str = ""
    marca: str = ""
    estilo: str = ""
    año_fabricacion: str = ""
    color: str = ""
    cilindrada_cc: str = ""
    valor_contrato: str = ""
    valor_hacienda: str = ""
    estado_actual: str = ""
    estado_tributario: str = ""
    propietario_id: str = ""
    propietario_nombre: str = ""
    serie_vin: str = ""
    motor: str = ""
    inscripcion_fecha: str = ""
    gravamenes: str = ""
    anotaciones: str = ""
    infracciones: str = ""
