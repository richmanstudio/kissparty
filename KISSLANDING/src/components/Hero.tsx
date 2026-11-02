import React from 'react';
import './Hero.css';

const Hero: React.FC = () => (
  <header className="tour-hero" id="top">
    <h1 className="tour-visually-hidden">KISS PARTY 2K17 TOUR — Хабаровск и Благовещенск</h1>
    <img
      className="tour-hero__banner"
      src="/media/kiss-party-2k17-tour.png"
      width="1672"
      height="941"
      alt="KISS PARTY 2K17 TOUR — огненный логотип на фоне многоэтажки, молний и фиолетового дыма"
      loading="eager"
      decoding="async"
    />
    <div className="tour-hero__footer">
      <p className="tour-hero__eyebrow">НОЯБРЬ 2026 / 2 ГОРОДА / 1 ТУР</p>
      <p className="tour-hero__tagline">ВЕРНЁМ ТЕБЯ В 2K17.</p>
      <a className="tour-hero__button" href="#cities">
        ВЫБРАТЬ ГОРОД <span aria-hidden="true">↓</span>
      </a>
    </div>
  </header>
);

export default Hero;
