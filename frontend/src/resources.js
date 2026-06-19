// NMEA 2000 PGN number → human-readable name
export const PGN_NAMES = {
  126992: 'System Time',
  127245: 'Rudder',
  127250: 'Vessel Heading',
  127251: 'Rate of Turn',
  127488: 'Engine Parameters',
  127508: 'Battery Status',
  128259: 'Speed, Water Ref.',
  128267: 'Water Depth',
  129025: 'Position',
  129026: 'COG & SOG',
  129029: 'GNSS Position',
  129033: 'Time & Date',
  129038: 'AIS Position',
  130306: 'Wind Data',
  130311: 'Environmental',
};

/** Return PGN name or fallback. */
export function pgnName(pgn) {
  return PGN_NAMES[pgn] || '';
}