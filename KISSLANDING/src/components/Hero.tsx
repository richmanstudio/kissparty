import React from 'react';
import './Hero.css';

const Hero: React.FC = () => {
  return (
    <section className="hero">
      <div className="hero-video-container">
        <video
          className="hero-video"
          autoPlay
          loop
          muted
          playsInline
          preload="auto"
          poster="/media/logo.png"
        >
          <source src="/media/IMG_7090.MP4" type="video/mp4" />
        </video>
        <div className="hero-overlay"></div>
        <div className="hero-chrome-overlay"></div>
      </div>
      <div className="hero-content">
        <div className="hero-text">
          <h1 className="hero-title">
            <span className="hero-title-main chrome-text">KISS PARTY</span>
          </h1>
          <p className="hero-subtitle chrome-text-small">
            Это история которую создаешь ты
          </p>
        </div>
      </div>
      <div className="hero-scroll-indicator">
        <div className="scroll-line"></div>
        <span>Scroll</span>
      </div>
    </section>
  );
};

export default Hero;

