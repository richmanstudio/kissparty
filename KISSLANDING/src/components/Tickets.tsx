import React from 'react';
import './Tickets.css';

const program = [
  'СПЕЦИАЛЬНАЯ ПРОГРАММА',
  'ЛУЧШИЕ DJ-СЕТЫ',
  'ФОТОЗОНА 2K17',
  'СЕКРЕТНЫЕ АРТИСТЫ',
  'ИНТЕРАКТИВЫ',
  'МЕРЧ KISS PARTY'
];

const Tickets: React.FC = () => (
  <section className="tour-experience" aria-labelledby="tour-experience-title">
    <p className="tour-experience__eyebrow">BACK TO 2017</p>
    <h2 id="tour-experience-title">ТОТ САМЫЙ <span>2K17.</span></h2>
    <p className="tour-experience__description">
      Музыка, которую ты помнишь. Атмосфера, которую невозможно повторить.
      Или тот самый 2017-й, который ты не успел застать.
    </p>
    <ul className="tour-experience__list">
      {program.map((item, index) => (
        <li key={item}><span>0{index + 1}</span>{item}</li>
      ))}
    </ul>
    <a href="#cities" className="tour-experience__link">
      ВЫБРАТЬ ГОРОД И КУПИТЬ БИЛЕТ <span aria-hidden="true">↗</span>
    </a>
    <a href="https://t.me/kisssparty" target="_blank" rel="noopener noreferrer" className="tour-experience__social">
      НОВОСТИ ТУРА В TELEGRAM
    </a>
  </section>
);

export default Tickets;
