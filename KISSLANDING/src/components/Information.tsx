import React from 'react';
import './Information.css';

interface TourStop {
  city: string;
  date: string;
  datetime: string;
  venue: string;
  address: string;
  localTime: string;
  price: string;
  ticketsUrl: string;
}

const stops: TourStop[] = [
  {
    city: 'ХАБАРОВСК',
    date: '14 НОЯБРЯ',
    datetime: '2026-11-14',
    venue: 'LOONA CLUB',
    address: 'ул. Тургенева, 46',
    localTime: '17:00',
    price: 'ОТ 690 ₽',
    ticketsUrl: 'https://habarovsk.qtickets.events/'
  },
  {
    city: 'БЛАГОВЕЩЕНСК',
    date: '21 НОЯБРЯ',
    datetime: '2026-11-21',
    venue: 'СПОТ CLUB',
    address: 'ул. Театральная, 170',
    localTime: '17:00',
    price: 'ОТ 590 ₽',
    ticketsUrl: 'https://blagoveshensk.qtickets.events/264731-kiss-party-2k17'
  }
];

const Information: React.FC = () => (
  <section className="tour-cities" id="cities" aria-labelledby="tour-cities-title">
    <div className="tour-cities__heading">
      <div>
        <p className="tour-cities__label">KISS PARTY 2K17 TOUR / 2026</p>
        <h2 id="tour-cities-title">ВЫБЕРИ <span>ГОРОД</span></h2>
      </div>
      <p className="tour-cities__intro">Один вайб. Две даты. Найди свой город и забирай билет.</p>
    </div>
    <div className="tour-cities__grid">
      {stops.map((stop, index) => (
        <article className="tour-stop" key={stop.city}>
          <div className="tour-stop__top">
            <span className="tour-stop__index">0{index + 1} / 02</span>
            <span className="tour-stop__age">14+</span>
          </div>
          <p className="tour-stop__date"><time dateTime={stop.datetime}>{stop.date}</time> <span>2026</span></p>
          <h3 className="tour-stop__city">{stop.city}</h3>
          <div className="tour-stop__details">
            <span><b>КЛУБ</b>{stop.venue}</span>
            <span><b>АДРЕС</b>{stop.address}</span>
            <span><b>ВРЕМЯ ПО АФИШЕ</b>{stop.localTime}</span>
          </div>
          <div className="tour-stop__bottom">
            <span className="tour-stop__price">{stop.price}</span>
            <a
              href={stop.ticketsUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="tour-stop__buy"
              aria-label={'Билеты на KISS PARTY 2K17 в городе ' + stop.city}
            >
              БИЛЕТЫ <span aria-hidden="true">↗</span>
            </a>
          </div>
        </article>
      ))}
    </div>
    <p className="tour-cities__time-note">На афишах указано 17:00, в билетном сервисе — 18:00. Перед посещением уточни время у организатора или в билете.</p>
  </section>
);

export default Information;
