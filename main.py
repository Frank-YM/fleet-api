"""
FLEET API - Sistema de gestión de flota de transporte
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
import sqlite3

# Database setup
DATABASE_URL = "sqlite:///fleet.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# =====================
# Models
# =====================

class Company(Base):
    __tablename__ = "companies"
    
    id = Column(String, primary_key=True)
    ruc = Column(String, unique=True)
    name = Column(String, nullable=False)
    address = Column(String)
    phone = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    vehicles = relationship("Vehicle", back_populates="company")
    drivers = relationship("Driver", back_populates="company")
    orders = relationship("Order", back_populates="company")
    documents = relationship("Document", back_populates="company")

class Vehicle(Base):
    __tablename__ = "vehicles"
    
    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("companies.id"))
    plate = Column(String, nullable=False)  # Placa única
    type = Column(String)  # tracto, carreta, etc
    brand = Column(String)
    model = Column(String)
    year = Column(String)
    vin = Column(String)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    company = relationship("Company", back_populates="vehicles")
    documents = relationship("Document", back_populates="vehicle")
    order_vehicles = relationship("OrderVehicle", back_populates="vehicle")

class Driver(Base):
    __tablename__ = "drivers"
    
    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("companies.id"))
    dni = Column(String, unique=True)
    name = Column(String, nullable=False)
    license_number = Column(String)
    license_type = Column(String)  # A, B, C, etc
    license_expiry = Column(String)
    phone = Column(String)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    company = relationship("Company", back_populates="drivers")
    documents = relationship("Document", back_populates="driver")
    order_assignments = relationship("OrderAssignment", back_populates="driver")

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("companies.id"))
    order_number = Column(String, unique=True)  # Número de serie de orden
    scop = Column(String)  # Número SCOP
    recipient = Column(String)  # Destinatario
    plant = Column(String)  # Planta
    product = Column(String)  # Producto transportado
    quantity = Column(String)  # Cantidad en galones
    date = Column(String)  # Fecha y hora
    status = Column(String, default="pending")  # pending, in_progress, completed, cancelled
    observations = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    company = relationship("Company", back_populates="orders")
    order_vehicles = relationship("OrderVehicle", back_populates="order")
    order_assignments = relationship("OrderAssignment", back_populates="order")

class OrderVehicle(Base):
    __tablename__ = "order_vehicles"
    
    id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey("orders.id"))
    vehicle_id = Column(String, ForeignKey("vehicles.id"))
    
    order = relationship("Order", back_populates="order_vehicles")
    vehicle = relationship("Vehicle", back_populates="order_vehicles")

class OrderAssignment(Base):
    __tablename__ = "order_assignments"
    
    id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey("orders.id"))
    driver_id = Column(String, ForeignKey("drivers.id"))
    
    order = relationship("Order", back_populates="order_assignments")
    driver = relationship("Driver", back_populates="order_assignments")

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("companies.id"))
    vehicle_id = Column(String, ForeignKey("vehicles.id"), nullable=True)
    driver_id = Column(String, ForeignKey("drivers.id"), nullable=True)
    
    doc_type = Column(String)  # soat, tive, license, antecedentes, etc
    title = Column(String)
    file_path = Column(String)
    expiry_date = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    company = relationship("Company", back_populates="documents")
    vehicle = relationship("Vehicle", back_populates="documents")
    driver = relationship("Driver", back_populates="documents")

# Create tables
Base.metadata.create_all(bind=engine)

# =====================
# API Endpoints
# =====================

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import uuid

app = FastAPI(title="Fleet API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def generate_id():
    return str(uuid.uuid4())[:8]

# Pydantic models
class CompanyCreate(BaseModel):
    name: str
    ruc: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None

class VehicleCreate(BaseModel):
    plate: str
    type: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    year: Optional[str] = None
    vin: Optional[str] = None

class DriverCreate(BaseModel):
    dni: str
    name: str
    license_number: Optional[str] = None
    license_type: Optional[str] = None
    license_expiry: Optional[str] = None
    phone: Optional[str] = None

class OrderCreate(BaseModel):
    order_number: str
    scop: Optional[str] = None
    recipient: Optional[str] = None  # Destinatario (ej: Petroperu S.A.)
    plant: Optional[str] = None  # Planta (ej: Terminal Mollendo)
    product: Optional[str] = None  # Producto transportado
    quantity: Optional[str] = None  # Cantidad en galones
    date: Optional[str] = None
    observations: Optional[str] = None
    vehicle_ids: Optional[list] = []
    driver_ids: Optional[list] = []

class DocumentCreate(BaseModel):
    doc_type: str
    title: str
    file_path: str
    expiry_date: Optional[str] = None
    vehicle_id: Optional[str] = None
    driver_id: Optional[str] = None

# =====================
# Company Endpoints
# =====================

@app.post("/api/companies")
def create_company(data: CompanyCreate, db: SessionLocal = Depends(get_db)):
    company = Company(
        id=generate_id(),
        name=data.name,
        ruc=data.ruc,
        address=data.address,
        phone=data.phone
    )
    db.add(company)
    db.commit()
    return {"success": True, "company": company}

@app.get("/api/companies")
def list_companies(db: SessionLocal = Depends(get_db)):
    companies = db.query(Company).all()
    return {"companies": companies}

@app.get("/api/companies/{company_id}")
def get_company(company_id: str, db: SessionLocal = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, message="Empresa no encontrada")
    return company

# =====================
# Vehicle Endpoints
# =====================

@app.post("/api/{company_id}/vehicles")
def create_vehicle(company_id: str, data: VehicleCreate, db: SessionLocal = Depends(get_db)):
    # Verify company exists
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, message="Empresa no encontrada")
    
    vehicle = Vehicle(
        id=generate_id(),
        company_id=company_id,
        plate=data.plate.upper(),
        type=data.type,
        brand=data.brand,
        model=data.model,
        year=data.year,
        vin=data.vin
    )
    db.add(vehicle)
    db.commit()
    return {"success": True, "vehicle": vehicle}

@app.get("/api/{company_id}/vehicles")
def list_vehicles(company_id: str, db: SessionLocal = Depends(get_db)):
    vehicles = db.query(Vehicle).filter(Vehicle.company_id == company_id).all()
    return {"vehicles": vehicles}

@app.get("/api/{company_id}/vehicles/{vehicle_id}")
def get_vehicle(company_id: str, vehicle_id: str, db: SessionLocal = Depends(get_db)):
    vehicle = db.query(Vehicle).filter(
        Vehicle.id == vehicle_id,
        Vehicle.company_id == company_id
    ).first()
    if not vehicle:
        raise HTTPException(status_code=404, message="Vehículo no encontrado")
    return vehicle

@app.delete("/api/{company_id}/vehicles/{vehicle_id}")
def delete_vehicle(company_id: str, vehicle_id: str, db: SessionLocal = Depends(get_db)):
    vehicle = db.query(Vehicle).filter(
        Vehicle.id == vehicle_id,
        Vehicle.company_id == company_id
    ).first()
    if not vehicle:
        raise HTTPException(status_code=404, message="Vehículo no encontrado")
    db.delete(vehicle)
    db.commit()
    return {"success": True, "deleted": vehicle_id}

# =====================
# Driver Endpoints
# =====================

@app.post("/api/{company_id}/drivers")
def create_driver(company_id: str, data: DriverCreate, db: SessionLocal = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, message="Empresa no encontrada")
    
    driver = Driver(
        id=generate_id(),
        company_id=company_id,
        dni=data.dni,
        name=data.name.upper(),
        license_number=data.license_number,
        license_type=data.license_type,
        license_expiry=data.license_expiry,
        phone=data.phone
    )
    db.add(driver)
    db.commit()
    return {"success": True, "driver": driver}

@app.get("/api/{company_id}/drivers")
def list_drivers(company_id: str, db: SessionLocal = Depends(get_db)):
    drivers = db.query(Driver).filter(Driver.company_id == company_id).all()
    return {"drivers": drivers}

# =====================
# Order Endpoints
# =====================

@app.post("/api/{company_id}/orders")
def create_order(company_id: str, data: OrderCreate, db: SessionLocal = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, message="Empresa no encontrada")
    
    order = Order(
        id=generate_id(),
        company_id=company_id,
        order_number=data.order_number,
        scop=data.scop,
        recipient=data.recipient,
        plant=data.plant,
        product=data.product,
        quantity=data.quantity,
        date=data.date,
        status="pending",
        observations=data.observations
    )
    db.add(order)
    
    # Add vehicles
    if data.vehicle_ids:
        for vid in data.vehicle_ids:
            ov = OrderVehicle(id=generate_id(), order_id=order.id, vehicle_id=vid)
            db.add(ov)
    
    # Add drivers
    if data.driver_ids:
        for did in data.driver_ids:
            oa = OrderAssignment(id=generate_id(), order_id=order.id, driver_id=did)
            db.add(oa)
    
    db.commit()
    return {"success": True, "order": order}

@app.get("/api/{company_id}/orders")
def list_orders(company_id: str, db: SessionLocal = Depends(get_db)):
    orders = db.query(Order).filter(Order.company_id == company_id).all()
    result = []
    for o in orders:
        order_data = {
            "id": o.id,
            "order_number": o.order_number,
            "scop": o.scop,
            "recipient": o.recipient,
            "plant": o.plant,
            "product": o.product,
            "quantity": o.quantity,
            "date": o.date,
            "status": o.status,
            "observations": o.observations,
            "vehicles": [db.query(Vehicle).filter(Vehicle.id == ov.vehicle_id).first() 
                        for ov in o.order_vehicles],
            "drivers": [db.query(Driver).filter(Driver.id == oa.driver_id).first()
                        for oa in o.order_assignments]
        }
        result.append(order_data)
    return {"orders": result}

# =====================
# PDF Generation - Orden de Retiro
# =====================
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from io import BytesIO

@app.get("/api/{company_id}/orders/{order_id}/pdf")
def generate_order_pdf(company_id: str, order_id: str, db: SessionLocal = Depends(get_db)):
    """Generate PDF for a specific order - minimalist design"""
    order = db.query(Order).filter(Order.id == order_id, Order.company_id == company_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    
    company = db.query(Company).filter(Company.id == company_id).first()
    
    vehicles = []
    for ov in order.order_vehicles:
        v = db.query(Vehicle).filter(Vehicle.id == ov.vehicle_id).first()
        if v:
            vehicles.append(v)
    
    drivers = []
    for oa in order.order_assignments:
        d = db.query(Driver).filter(Driver.id == oa.driver_id).first()
        if d:
            drivers.append(d)
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=15*mm, bottomMargin=15*mm, leftMargin=15*mm, rightMargin=15*mm)
    elements = []
    
    styles = getSampleStyleSheet()
    
    # Colors - minimalist
    dark = colors.HexColor('#1A1A1A')
    gray = colors.HexColor('#6B7280')
    light_gray = colors.HexColor('#F3F4F6')
    border = colors.HexColor('#E5E7EB')
    
    # Minimalist Styles
    company_style = ParagraphStyle('Company', parent=styles['Normal'], fontSize=13, textColor=dark, fontName='Helvetica-Bold', alignment=1, spaceAfter=2)
    ruc_style = ParagraphStyle('RUC', parent=styles['Normal'], fontSize=8, textColor=gray, alignment=1)
    order_title_style = ParagraphStyle('OT', parent=styles['Normal'], fontSize=11, textColor=dark, fontName='Helvetica-Bold', alignment=1)
    order_num_style = ParagraphStyle('ON', parent=styles['Normal'], fontSize=9, textColor=gray, alignment=1)
    section_style = ParagraphStyle('Section', parent=styles['Normal'], fontSize=7, textColor=gray, fontName='Helvetica-Bold', spaceBefore=4, spaceAfter=2)
    value_style = ParagraphStyle('Value', parent=styles['Normal'], fontSize=9, textColor=dark, fontName='Helvetica')
    sig_label_style = ParagraphStyle('SigLabel', parent=styles['Normal'], fontSize=7, textColor=gray, alignment=1)
    
    # Logo (LEFT) | Company Name (CENTER) | Order Number (RIGHT)
    base_dir = os.path.expanduser("~/Documents/FLEET")
    logo_path = os.path.join(base_dir, "TransportesJesusEsVida", "logo.png")
    try:
        logo_img = Image(logo_path, width=20*mm, height=20*mm)
    except:
        logo_img = Paragraph("", styles['Normal'])
    
    header_row = Table([
        [logo_img, 
         Paragraph(company.name, ParagraphStyle('CN', parent=styles['Normal'], fontSize=13, textColor=dark, fontName='Helvetica-Bold', alignment=1)),
         Paragraph(f"N° {order.order_number}", ParagraphStyle('ON', parent=styles['Normal'], fontSize=11, textColor=dark, fontName='Helvetica-Bold', alignment=2))]
    ], colWidths=[26*mm, 120*mm, 34*mm])
    header_row.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (0,0), 0),
        ('RIGHTPADDING', (0,0), (0,0), 8),
        ('LEFTPADDING', (1,0), (1,0), 5),
        ('LEFTPADDING', (2,0), (2,0), 5),
    ]))
    elements.append(header_row)
    
    # RUC and address below company name
    elements.append(Paragraph(f"RUC: {company.ruc or 'N/A'} — {company.address or ''}", ParagraphStyle('RA', parent=styles['Normal'], fontSize=7, textColor=gray, alignment=1)))
    elements.append(Spacer(1, 5*mm))
    elements.append(Spacer(1, 5*mm))
    
    # 2-column layout: Info (left) + Driver (right)
    if drivers and vehicles:
        d = drivers[0]
        left_col = [
            [Paragraph("INFORMACIÓN", section_style)],
            ["Destinatario", order.recipient or "—"],
            ["Fecha", order.date or "—"],
            ["Planta", order.plant or "—"],
        ]
        right_col = [
            [Paragraph("CONDUCTOR", section_style)],
            [d.name, f"DNI: {d.dni}"],
            [f"Licencia: {d.license_number or '—'} ({d.license_type or '—'})", ""],
        ]
        # Build left table
        left_data = [[Paragraph("INFORMACIÓN", section_style)]]
        left_data.append([Paragraph("Destinatario", ParagraphStyle('L', parent=styles['Normal'], fontSize=7, textColor=gray)), Paragraph(order.recipient or "—", value_style)])
        left_data.append([Paragraph("Fecha", ParagraphStyle('L', parent=styles['Normal'], fontSize=7, textColor=gray)), Paragraph(order.date or "—", value_style)])
        left_data.append([Paragraph("Planta", ParagraphStyle('L', parent=styles['Normal'], fontSize=7, textColor=gray)), Paragraph(order.plant or "—", value_style)])
        left_table = Table(left_data, colWidths=[25*mm, 62*mm])
        left_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('LINEBELOW', (0,1), (-1,2), 0.2, border),
        ]))
        
        # Build right table
        right_data = [[Paragraph("CONDUCTOR", section_style)]]
        right_data.append([Paragraph("Nombre", ParagraphStyle('L', parent=styles['Normal'], fontSize=7, textColor=gray)), Paragraph(d.name, value_style)])
        right_data.append([Paragraph("DNI", ParagraphStyle('L', parent=styles['Normal'], fontSize=7, textColor=gray)), Paragraph(d.dni, value_style)])
        right_data.append([Paragraph("Licencia", ParagraphStyle('L', parent=styles['Normal'], fontSize=7, textColor=gray)), Paragraph(f"{d.license_number or '—'} ({d.license_type or '—'})", value_style)])
        right_table = Table(right_data, colWidths=[22*mm, 65*mm])
        right_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('LINEBELOW', (0,1), (-1,2), 0.2, border),
        ]))
        
        # 2-column layout
        two_col = Table([[left_table, right_table]], colWidths=[90*mm, 90*mm])
        two_col.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))
        elements.append(two_col)
        elements.append(Spacer(1, 4*mm))
    else:
        # Fallback to sequential if no driver
        info_data = [["Destinatario", order.recipient or "—"], ["Fecha", order.date or "—"], ["Planta", order.plant or "—"]]
        info_table = Table(info_data, colWidths=[25*mm, 62*mm])
        info_table.setStyle(TableStyle([
            ('TEXTCOLOR', (0,0), (0,-1), gray),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('LINEBELOW', (0,0), (-1,-2), 0.2, border),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 4*mm))
    
    # Vehicles Section (2 columns: Vehicle 1 | Vehicle 2)
    if vehicles:
        elements.append(Paragraph("VEHÍCULOS", section_style))
        
        # Build vehicle cells
        veh_cells = []
        for i, v in enumerate(vehicles, 1):
            cell = Table([
                [Paragraph(f"Vehículo {i}", ParagraphStyle('VH', parent=styles['Normal'], fontSize=7, textColor=gray))],
                [Paragraph(f"{v.plate}", ParagraphStyle('VP', parent=styles['Normal'], fontSize=10, textColor=dark, fontName='Helvetica-Bold'))],
                [Paragraph(f"{v.type or '—'} — {v.brand or ''} {v.model or ''}".strip(), ParagraphStyle('VD', parent=styles['Normal'], fontSize=7, textColor=gray))],
            ], colWidths=[88*mm])
            cell.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), light_gray),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('LEFTPADDING', (0,0), (-1,-1), 8),
                ('RIGHTPADDING', (0,0), (-1,-1), 8),
                ('ROUNDEDCORNERS', [4, 4, 4, 4]),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ]))
            veh_cells.append(cell)
        
        # Place vehicles side by side in one row
        if len(veh_cells) == 1:
            veh_table = Table([[veh_cells[0]]], colWidths=[180*mm])
        else:
            veh_table = Table([veh_cells], colWidths=[90*mm, 90*mm])
        
        veh_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (0,-1), 4),
            ('RIGHTPADDING', (1,-1), (1,-1), 0),
        ]))
        elements.append(veh_table)
        elements.append(Spacer(1, 4*mm))
    
    # Info and Driver in 2-column layout above
    
    # Products Section (with SCOP in table only)
    if vehicles:
        elements.append(Paragraph("PRODUCTOS", section_style))
        prod_data = [["SCOP", "Producto", "Cantidad (Gal)"]]
        prod_data.append([order.scop or "—", order.product or "—", order.quantity or "—"])
        prod_table = Table(prod_data, colWidths=[35*mm, 115*mm, 30*mm])
        prod_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), light_gray),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0,0), (-1,0), gray),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('ALIGN', (0,0), (0,-1), 'CENTER'),
            ('ALIGN', (2,0), (2,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.3, border),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('BACKGROUND', (0,1), (-1,-1), colors.white),
        ]))
        elements.append(prod_table)
        elements.append(Spacer(1, 8*mm))
    
    # Signature (only Representative)
    elements.append(Spacer(1, 15*mm))
    # Signature (only Representative)
    elements.append(Spacer(1, 20*mm))
    sig_data = [
        ["_________________________________"],
        [Paragraph("Firma Representante Legal", sig_label_style)],
    ]
    sig_table = Table(sig_data, colWidths=[90*mm])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    elements.append(sig_table)
    
    doc.build(elements)
    buffer.seek(0)
    
    filename = f"Orden_{order.order_number}_{company.name.replace(' ', '_')}.pdf"
    return StreamingResponse(buffer, media_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename={filename}'
    })

# =====================
# Document Endpoints
# =====================

@app.post("/api/{company_id}/documents")
def create_document(company_id: str, data: DocumentCreate, db: SessionLocal = Depends(get_db)):
    doc = Document(
        id=generate_id(),
        company_id=company_id,
        doc_type=data.doc_type,
        title=data.title,
        file_path=data.file_path,
        expiry_date=data.expiry_date,
        vehicle_id=data.vehicle_id,
        driver_id=data.driver_id
    )
    db.add(doc)
    db.commit()
    return {"success": True, "document": doc}

@app.delete("/api/{company_id}/documents/{document_id}")
def delete_document(company_id: str, document_id: str, db: SessionLocal = Depends(get_db)):
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.company_id == company_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    db.delete(doc)
    db.commit()
    return {"success": True, "deleted": document_id}

@app.get("/api/{company_id}/documents")
def list_documents(company_id: str, doc_type: Optional[str] = None, db: SessionLocal = Depends(get_db)):
    query = db.query(Document).filter(Document.company_id == company_id)
    if doc_type:
        query = query.filter(Document.doc_type == doc_type)
    documents = query.all()
    return {"documents": documents}

@app.get("/api/{company_id}/documents/expiring")
def documents_expiring(company_id: str, db: SessionLocal = Depends(get_db)):
    """Get documents expiring in next 30 days"""
    from datetime import datetime, timedelta
    today = datetime.now().strftime("%d/%m/%Y")
    # Simple filter - in production would parse dates properly
    docs = db.query(Document).filter(Document.company_id == company_id).all()
    return {"documents": docs}

@app.get("/health")
def health():
    return {"status": "ok", "api": "Fleet API v1.0"}

if __name__ == "__main__":
    import uvicorn
    print("🚀 Fleet API starting...")
    print("📍 http://localhost:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="debug")
# Folder name mapping (folder name -> DB company name lookup)
def get_folder_name(company_id):
    """Map company ID to folder name"""
    conn = sqlite3.connect("fleet.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT name FROM companies WHERE id = ?", (company_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return None
    
    company_name = row[0].upper()
    
    # Map DB names to folder names
    folder_map = {
        "TRANSPORTES JESUS ES VIDA": "TransportesJesusEsVida",
        "SERVICIO DE TRANSPORTES DANIEL": "STDaniel",
        "TRANSPORTES JOSUE": "TransportesJosue",
    }
    
    return folder_map.get(company_name, company_name)

# Simple test at root level
@app.get("/test123")
async def test123():
    return {"test": "works 123"}

# Debug endpoint - must be before the path endpoint
@app.get("/debug/files/test")
async def debug_test_files():
    return {"status": "debug working"}

@app.get("/files/{company_id}/{filename:path}")
async def serve_file(company_id: str, filename: str):
    """Serve document files"""
    from fastapi.responses import FileResponse, JSONResponse
    from urllib.parse import unquote
    import os
    
    # Decode URL-encoded characters
    filename = unquote(filename)
    
    folder_name = get_folder_name(company_id)
    if not folder_name:
        return JSONResponse({"error": "Company not found", "company_id": company_id})
    
    base_path = os.path.expanduser("~/Documents/FLEET")
    
    # Try with folder name
    file_path = os.path.join(base_path, folder_name, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    
    # Try just the file relative to company folder
    test_path = os.path.join(base_path, folder_name, filename.replace("/", "_"))
    
    return JSONResponse({
        "error": "File not found",
        "company_id": company_id,
        "folder": folder_name,
        "filename": filename,
        "tried_path": file_path,
        "exists": os.path.exists(file_path),
        "folder_exists": os.path.exists(os.path.join(base_path, folder_name)),
        "files_in_folder": os.listdir(os.path.join(base_path, folder_name)) if os.path.exists(os.path.join(base_path, folder_name)) else []
    })
    return {"error": "File not found"}
