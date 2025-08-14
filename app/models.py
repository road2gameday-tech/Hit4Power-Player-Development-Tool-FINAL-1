
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Instructor(Base):
    __tablename__ = "instructors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    code = Column(String, unique=True, index=True)

    favorites = relationship("InstructorPlayer", back_populates="instructor", cascade="all, delete")

class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    phone = Column(String, nullable=True)
    login_code = Column(String, unique=True, index=True)
    avatar_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    metrics = relationship("Metric", back_populates="player", cascade="all, delete")
    notes = relationship("CoachNote", back_populates="player", cascade="all, delete")
    assigned_drills = relationship("AssignedDrill", back_populates="player", cascade="all, delete")

class InstructorPlayer(Base):
    __tablename__ = "instructor_players"
    id = Column(Integer, primary_key=True, index=True)
    instructor_id = Column(Integer, ForeignKey("instructors.id"))
    player_id = Column(Integer, ForeignKey("players.id"))
    is_favorite = Column(Boolean, default=False)

    instructor = relationship("Instructor", back_populates="favorites")
    player = relationship("Player")

class Metric(Base):
    __tablename__ = "metrics"
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    date = Column(DateTime, default=datetime.utcnow)
    exit_velocity = Column(Float, nullable=True)
    launch_angle = Column(Float, nullable=True)
    spin_rate = Column(Float, nullable=True)

    player = relationship("Player", back_populates="metrics")

class CoachNote(Base):
    __tablename__ = "coach_notes"
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    instructor_id = Column(Integer, ForeignKey("instructors.id"))
    content = Column(Text, nullable=False)
    shared_to_player = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    player = relationship("Player", back_populates="notes")

class Drill(Base):
    __tablename__ = "drills"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    uploader_instructor_id = Column(Integer, ForeignKey("instructors.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

class AssignedDrill(Base):
    __tablename__ = "assigned_drills"
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    drill_id = Column(Integer, ForeignKey("drills.id"))
    assigned_at = Column(DateTime, default=datetime.utcnow)

    player = relationship("Player", back_populates="assigned_drills")
