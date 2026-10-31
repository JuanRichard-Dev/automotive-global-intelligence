'use client';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Check, ChevronDown, Search } from 'lucide-react';

type Country = { value: string; label: string; available: boolean };
const normalize = (s: string) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');

export function CountrySelect({
  value, items, onChange,
}: {
  value: string;
  items: Country[];
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [term, setTerm] = useState('');
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const selected = items.find(x => x.value === value);
  const matches = useMemo(() => {
    const q = normalize(term.trim());
    return items.filter(x => !q || normalize(x.label + ' ' + x.value).includes(q));
  }, [items, term]);
  const available = matches.filter(x => x.available);
  const unavailable = matches.filter(x => !x.available);
  const choices = [...available, ...unavailable];

  useEffect(() => {
    if (!open) return;
    const close = (e: PointerEvent) => {
      if (root.current && !root.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', close);
    search.current?.focus();
    return () => document.removeEventListener('pointerdown', close);
  }, [open]);

  const choose = (country: Country) => {
    onChange(country.value);
    setOpen(false);
    setTerm('');
    trigger.current?.focus();
  };
  const openMenu = () => {
    setOpen(v => !v);
    setTerm('');
    setActive(0);
  };
  const handleKeys = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      e.preventDefault(); setOpen(false); trigger.current?.focus();
    } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      setActive(x => Math.max(0, Math.min(choices.length - 1, x + (e.key === 'ArrowDown' ? 1 : -1))));
    } else if (e.key === 'Enter' && choices[active]) {
      e.preventDefault(); choose(choices[active]);
    }
  };
  useEffect(() => {
    if (open) list.current?.querySelector('[data-active="true"]')?.scrollIntoView({ block: 'nearest' });
  }, [open, active]);

  let index = -1;
  return (
    <div className="filter country-filter" ref={root}>
      <span className="filter-label">PAÍS</span>
      <button type="button" ref={trigger} className="country-trigger"
        aria-label="País" aria-haspopup="listbox" aria-expanded={open}
        aria-controls="atlas-country-list" onClick={openMenu}>
        <span>{selected?.label || 'Selecione um país'}</span>
        <ChevronDown size={14} aria-hidden="true" />
      </button>
      {open && (
        <div className="country-menu">
          <div className="country-search">
            <Search size={16} aria-hidden="true" />
            <input ref={search} type="search" value={term} onChange={e => {setTerm(e.target.value);setActive(0);}}
              onKeyDown={handleKeys} aria-label="Buscar país" aria-controls="atlas-country-list"
              placeholder="Buscar país ou código..." autoComplete="off" role="combobox"
              aria-expanded={open} aria-autocomplete="list"
              aria-activedescendant={choices[active] ? 'country-' + choices[active].value : undefined} />
          </div>
          <div className="country-options" id="atlas-country-list" ref={list} role="listbox" aria-label="Países">
            {choices.length === 0 && <p className="country-empty">Nenhum país encontrado.</p>}
            {available.length > 0 && <div className="country-group-label">COM DADOS DISPONÍVEIS ({available.length})</div>}
            {available.map(country => {
              index++;
              const current = index;
              return (
                <button type="button" role="option" id={'country-' + country.value} key={country.value}
                  className="country-option" aria-selected={country.value === value} data-active={current === active}
                  onMouseEnter={() => setActive(current)} onClick={() => choose(country)}>
                  <span>{country.label}</span>
                  {country.value === value && <Check size={15} aria-hidden="true" />}
                </button>
              );
            })}
            {unavailable.length > 0 && <div className="country-group-label">SEM REGISTROS AUTOMOTIVOS ({unavailable.length})</div>}
            {unavailable.map(country => {
              index++;
              const current = index;
              return (
                <button type="button" role="option" id={'country-' + country.value} key={country.value}
                  className="country-option unavailable" aria-selected={country.value === value} data-active={current === active}
                  onMouseEnter={() => setActive(current)} onClick={() => choose(country)}>
                  <span>{country.label}</span>
                  <small>{country.value === value ? <Check size={15} aria-hidden="true" /> : 'Sem dados'}</small>
                </button>
              );
            })}
          </div>
          <p className="country-menu-footer">{choices.length} países encontrados · ↑ ↓ para navegar</p>
        </div>
      )}
    </div>
  );
}
