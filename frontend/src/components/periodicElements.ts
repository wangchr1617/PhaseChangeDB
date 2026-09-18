export interface ElementInfo {
  number: number
  symbol: string
  name: string
  zh: string
  category: 'nonmetal' | 'noble' | 'alkali' | 'alkaline' | 'metalloid' | 'halogen' | 'transition' | 'post-transition' | 'lanthanide' | 'actinide'
  row: number
  col: number
}

export const PERIODIC_ELEMENTS: ElementInfo[] = [
  // Period 1
  { number: 1, symbol: 'H', name: 'Hydrogen', zh: '氢', category: 'nonmetal', row: 1, col: 1 },
  { number: 2, symbol: 'He', name: 'Helium', zh: '氦', category: 'noble', row: 1, col: 18 },

  // Period 2
  { number: 3, symbol: 'Li', name: 'Lithium', zh: '锂', category: 'alkali', row: 2, col: 1 },
  { number: 4, symbol: 'Be', name: 'Beryllium', zh: '铍', category: 'alkaline', row: 2, col: 2 },
  { number: 5, symbol: 'B', name: 'Boron', zh: '硼', category: 'metalloid', row: 2, col: 13 },
  { number: 6, symbol: 'C', name: 'Carbon', zh: '碳', category: 'nonmetal', row: 2, col: 14 },
  { number: 7, symbol: 'N', name: 'Nitrogen', zh: '氮', category: 'nonmetal', row: 2, col: 15 },
  { number: 8, symbol: 'O', name: 'Oxygen', zh: '氧', category: 'nonmetal', row: 2, col: 16 },
  { number: 9, symbol: 'F', name: 'Fluorine', zh: '氟', category: 'halogen', row: 2, col: 17 },
  { number: 10, symbol: 'Ne', name: 'Neon', zh: '氖', category: 'noble', row: 2, col: 18 },

  // Period 3
  { number: 11, symbol: 'Na', name: 'Sodium', zh: '钠', category: 'alkali', row: 3, col: 1 },
  { number: 12, symbol: 'Mg', name: 'Magnesium', zh: '镁', category: 'alkaline', row: 3, col: 2 },
  { number: 13, symbol: 'Al', name: 'Aluminium', zh: '铝', category: 'post-transition', row: 3, col: 13 },
  { number: 14, symbol: 'Si', name: 'Silicon', zh: '硅', category: 'metalloid', row: 3, col: 14 },
  { number: 15, symbol: 'P', name: 'Phosphorus', zh: '磷', category: 'nonmetal', row: 3, col: 15 },
  { number: 16, symbol: 'S', name: 'Sulfur', zh: '硫', category: 'nonmetal', row: 3, col: 16 },
  { number: 17, symbol: 'Cl', name: 'Chlorine', zh: '氯', category: 'halogen', row: 3, col: 17 },
  { number: 18, symbol: 'Ar', name: 'Argon', zh: '氩', category: 'noble', row: 3, col: 18 },

  // Period 4
  { number: 19, symbol: 'K', name: 'Potassium', zh: '钾', category: 'alkali', row: 4, col: 1 },
  { number: 20, symbol: 'Ca', name: 'Calcium', zh: '钙', category: 'alkaline', row: 4, col: 2 },
  { number: 21, symbol: 'Sc', name: 'Scandium', zh: '钪', category: 'transition', row: 4, col: 3 },
  { number: 22, symbol: 'Ti', name: 'Titanium', zh: '钛', category: 'transition', row: 4, col: 4 },
  { number: 23, symbol: 'V', name: 'Vanadium', zh: '钒', category: 'transition', row: 4, col: 5 },
  { number: 24, symbol: 'Cr', name: 'Chromium', zh: '铬', category: 'transition', row: 4, col: 6 },
  { number: 25, symbol: 'Mn', name: 'Manganese', zh: '锰', category: 'transition', row: 4, col: 7 },
  { number: 26, symbol: 'Fe', name: 'Iron', zh: '铁', category: 'transition', row: 4, col: 8 },
  { number: 27, symbol: 'Co', name: 'Cobalt', zh: '钴', category: 'transition', row: 4, col: 9 },
  { number: 28, symbol: 'Ni', name: 'Nickel', zh: '镍', category: 'transition', row: 4, col: 10 },
  { number: 29, symbol: 'Cu', name: 'Copper', zh: '铜', category: 'transition', row: 4, col: 11 },
  { number: 30, symbol: 'Zn', name: 'Zinc', zh: '锌', category: 'transition', row: 4, col: 12 },
  { number: 31, symbol: 'Ga', name: 'Gallium', zh: '镓', category: 'post-transition', row: 4, col: 13 },
  { number: 32, symbol: 'Ge', name: 'Germanium', zh: '锗', category: 'metalloid', row: 4, col: 14 },
  { number: 33, symbol: 'As', name: 'Arsenic', zh: '砷', category: 'metalloid', row: 4, col: 15 },
  { number: 34, symbol: 'Se', name: 'Selenium', zh: '硒', category: 'nonmetal', row: 4, col: 16 },
  { number: 35, symbol: 'Br', name: 'Bromine', zh: '溴', category: 'halogen', row: 4, col: 17 },
  { number: 36, symbol: 'Kr', name: 'Krypton', zh: '氪', category: 'noble', row: 4, col: 18 },

  // Period 5
  { number: 37, symbol: 'Rb', name: 'Rubidium', zh: '铷', category: 'alkali', row: 5, col: 1 },
  { number: 38, symbol: 'Sr', name: 'Strontium', zh: '锶', category: 'alkaline', row: 5, col: 2 },
  { number: 39, symbol: 'Y', name: 'Yttrium', zh: '钇', category: 'transition', row: 5, col: 3 },
  { number: 40, symbol: 'Zr', name: 'Zirconium', zh: '锆', category: 'transition', row: 4, col: 4 },
  { number: 41, symbol: 'Nb', name: 'Niobium', zh: '铌', category: 'transition', row: 5, col: 5 },
  { number: 42, symbol: 'Mo', name: 'Molybdenum', zh: '钼', category: 'transition', row: 5, col: 6 },
  { number: 43, symbol: 'Tc', name: 'Technetium', zh: '锝', category: 'transition', row: 5, col: 7 },
  { number: 44, symbol: 'Ru', name: 'Ruthenium', zh: '钌', category: 'transition', row: 5, col: 8 },
  { number: 45, symbol: 'Rh', name: 'Rhodium', zh: '铑', category: 'transition', row: 5, col: 9 },
  { number: 46, symbol: 'Pd', name: 'Palladium', zh: '钯', category: 'transition', row: 5, col: 10 },
  { number: 47, symbol: 'Ag', name: 'Silver', zh: '银', category: 'transition', row: 5, col: 11 },
  { number: 48, symbol: 'Cd', name: 'Cadmium', zh: '镉', category: 'transition', row: 5, col: 12 },
  { number: 49, symbol: 'In', name: 'Indium', zh: '铟', category: 'post-transition', row: 5, col: 13 },
  { number: 50, symbol: 'Sn', name: 'Tin', zh: '锡', category: 'post-transition', row: 5, col: 14 },
  { number: 51, symbol: 'Sb', name: 'Antimony', zh: '锑', category: 'metalloid', row: 5, col: 15 },
  { number: 52, symbol: 'Te', name: 'Tellurium', zh: '碲', category: 'metalloid', row: 5, col: 16 },
  { number: 53, symbol: 'I', name: 'Iodine', zh: '碘', category: 'halogen', row: 5, col: 17 },
  { number: 54, symbol: 'Xe', name: 'Xenon', zh: '氙', category: 'noble', row: 5, col: 18 },

  // Period 6
  { number: 55, symbol: 'Cs', name: 'Caesium', zh: '铯', category: 'alkali', row: 6, col: 1 },
  { number: 56, symbol: 'Ba', name: 'Barium', zh: '钡', category: 'alkaline', row: 6, col: 2 },
  { number: 72, symbol: 'Hf', name: 'Hafnium', zh: '铪', category: 'transition', row: 6, col: 4 },
  { number: 73, symbol: 'Ta', name: 'Tantalum', zh: '钽', category: 'transition', row: 6, col: 5 },
  { number: 74, symbol: 'W', name: 'Tungsten', zh: '钨', category: 'transition', row: 6, col: 6 },
  { number: 75, symbol: 'Re', name: 'Rhenium', zh: '铼', category: 'transition', row: 6, col: 7 },
  { number: 76, symbol: 'Os', name: 'Osmium', zh: '锇', category: 'transition', row: 6, col: 8 },
  { number: 77, symbol: 'Ir', name: 'Iridium', zh: '铱', category: 'transition', row: 6, col: 9 },
  { number: 78, symbol: 'Pt', name: 'Platinum', zh: '铂', category: 'transition', row: 6, col: 10 },
  { number: 79, symbol: 'Au', name: 'Gold', zh: '金', category: 'transition', row: 6, col: 11 },
  { number: 80, symbol: 'Hg', name: 'Mercury', zh: '汞', category: 'transition', row: 6, col: 12 },
  { number: 81, symbol: 'Tl', name: 'Thallium', zh: '铊', category: 'post-transition', row: 6, col: 13 },
  { number: 82, symbol: 'Pb', name: 'Lead', zh: '铅', category: 'post-transition', row: 6, col: 14 },
  { number: 83, symbol: 'Bi', name: 'Bismuth', zh: '铋', category: 'post-transition', row: 6, col: 15 },
  { number: 84, symbol: 'Po', name: 'Polonium', zh: '钋', category: 'post-transition', row: 6, col: 16 },
  { number: 85, symbol: 'At', name: 'Astatine', zh: '砹', category: 'halogen', row: 6, col: 17 },
  { number: 86, symbol: 'Rn', name: 'Radon', zh: '氡', category: 'noble', row: 6, col: 18 },

  // Period 7
  { number: 87, symbol: 'Fr', name: 'Francium', zh: '钫', category: 'alkali', row: 7, col: 1 },
  { number: 88, symbol: 'Ra', name: 'Radium', zh: '镭', category: 'alkaline', row: 7, col: 2 },
  { number: 104, symbol: 'Rf', name: 'Rutherfordium', zh: '𬬻', category: 'transition', row: 7, col: 4 },
  { number: 105, symbol: 'Db', name: 'Dubnium', zh: '𬭊', category: 'transition', row: 7, col: 5 },
  { number: 106, symbol: 'Sg', name: 'Seaborgium', zh: '𬭳', category: 'transition', row: 7, col: 6 },
  { number: 107, symbol: 'Bh', name: 'Bohrium', zh: '𬭛', category: 'transition', row: 7, col: 7 },
  { number: 108, symbol: 'Hs', name: 'Hassium', zh: '𬭶', category: 'transition', row: 7, col: 8 },
  { number: 109, symbol: 'Mt', name: 'Meitnerium', zh: '鿏', category: 'transition', row: 7, col: 9 },
  { number: 110, symbol: 'Ds', name: 'Darmstadtium', zh: '𬭚', category: 'transition', row: 7, col: 10 },
  { number: 111, symbol: 'Rg', name: 'Roentgenium', zh: '𬬭', category: 'transition', row: 7, col: 11 },
  { number: 112, symbol: 'Cn', name: 'Copernicium', zh: '鎶', category: 'transition', row: 7, col: 12 },
  { number: 113, symbol: 'Nh', name: 'Nihonium', zh: '鿭', category: 'post-transition', row: 7, col: 13 },
  { number: 114, symbol: 'Fl', name: 'Flerovium', zh: '𫓧', category: 'post-transition', row: 7, col: 14 },
  { number: 115, symbol: 'Mc', name: 'Moscovium', zh: '镆', category: 'post-transition', row: 7, col: 15 },
  { number: 116, symbol: 'Lv', name: 'Livermorium', zh: '𫟼', category: 'post-transition', row: 7, col: 16 },
  { number: 117, symbol: 'Ts', name: 'Tennessine', zh: '鿬', category: 'halogen', row: 7, col: 17 },
  { number: 118, symbol: 'Og', name: 'Oganesson', zh: '鿫', category: 'noble', row: 7, col: 18 },

  // Lanthanides (Row 8, cols 4 to 18)
  { number: 57, symbol: 'La', name: 'Lanthanum', zh: '镧', category: 'lanthanide', row: 8, col: 4 },
  { number: 58, symbol: 'Ce', name: 'Cerium', zh: '铈', category: 'lanthanide', row: 8, col: 5 },
  { number: 59, symbol: 'Pr', name: 'Praseodymium', zh: '镨', category: 'lanthanide', row: 8, col: 6 },
  { number: 60, symbol: 'Nd', name: 'Neodymium', zh: '钕', category: 'lanthanide', row: 8, col: 7 },
  { number: 61, symbol: 'Pm', name: 'Promethium', zh: '钷', category: 'lanthanide', row: 8, col: 8 },
  { number: 62, symbol: 'Sm', name: 'Samarium', zh: '钐', category: 'lanthanide', row: 8, col: 9 },
  { number: 63, symbol: 'Eu', name: 'Europium', zh: '铕', category: 'lanthanide', row: 8, col: 10 },
  { number: 64, symbol: 'Gd', name: 'Gadolinium', zh: '钆', category: 'lanthanide', row: 8, col: 11 },
  { number: 65, symbol: 'Tb', name: 'Terbium', zh: '铽', category: 'lanthanide', row: 8, col: 12 },
  { number: 66, symbol: 'Dy', name: 'Dysprosium', zh: '镝', category: 'lanthanide', row: 8, col: 13 },
  { number: 67, symbol: 'Ho', name: 'Holmium', zh: '钬', category: 'lanthanide', row: 8, col: 14 },
  { number: 68, symbol: 'Er', name: 'Erbium', zh: '铒', category: 'lanthanide', row: 8, col: 15 },
  { number: 69, symbol: 'Tm', name: 'Thulium', zh: '铥', category: 'lanthanide', row: 8, col: 16 },
  { number: 70, symbol: 'Yb', name: 'Ytterbium', zh: '镱', category: 'lanthanide', row: 8, col: 17 },
  { number: 71, symbol: 'Lu', name: 'Lutetium', zh: '镥', category: 'lanthanide', row: 8, col: 18 },

  // Actinides (Row 9, cols 4 to 18)
  { number: 89, symbol: 'Ac', name: 'Actinium', zh: '锕', category: 'actinide', row: 9, col: 4 },
  { number: 90, symbol: 'Th', name: 'Thorium', zh: '钍', category: 'actinide', row: 9, col: 5 },
  { number: 91, symbol: 'Pa', name: 'Protactinium', zh: '镤', category: 'actinide', row: 9, col: 6 },
  { number: 92, symbol: 'U', name: 'Uranium', zh: '铀', category: 'actinide', row: 9, col: 7 },
  { number: 93, symbol: 'Np', name: 'Neptunium', zh: '镎', category: 'actinide', row: 9, col: 8 },
  { number: 94, symbol: 'Pu', name: 'Plutonium', zh: '钚', category: 'actinide', row: 9, col: 9 },
  { number: 95, symbol: 'Am', name: 'Americium', zh: '镅', category: 'actinide', row: 9, col: 10 },
  { number: 96, symbol: 'Cm', name: 'Curium', zh: '锔', category: 'actinide', row: 9, col: 11 },
  { number: 97, symbol: 'Bk', name: 'Berkelium', zh: '锫', category: 'actinide', row: 9, col: 12 },
  { number: 98, symbol: 'Cf', name: 'Californium', zh: '锎', category: 'actinide', row: 9, col: 13 },
  { number: 99, symbol: 'Es', name: 'Einsteinium', zh: '锿', category: 'actinide', row: 9, col: 14 },
  { number: 100, symbol: 'Fm', name: 'Fermium', zh: '镄', category: 'actinide', row: 9, col: 15 },
  { number: 101, symbol: 'Md', name: 'Mendelevium', zh: '钔', category: 'actinide', row: 9, col: 16 },
  { number: 102, symbol: 'No', name: 'Nobelium', zh: '锘', category: 'actinide', row: 9, col: 17 },
  { number: 103, symbol: 'Lr', name: 'Lawrencium', zh: '铹', category: 'actinide', row: 9, col: 18 },
]
