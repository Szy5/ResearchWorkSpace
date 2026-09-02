% Huawei-style technical report class
% (Unofficial)

\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{huawei_cloud}[Huawei technical report]
\LoadClassWithOptions{article}
%\pdfoutput=1
\RequirePackage[top=2.0cm,bottom=2.0cm,left=2.5cm,right=2.5cm,columnsep=0.65cm]{geometry}
\RequirePackage[T1]{fontenc}
\RequirePackage{microtype}
\RequirePackage{setspace}
\RequirePackage{ragged2e}
\RequirePackage{parskip}
\RequirePackage{hyphenat}
\RequirePackage{etoolbox}
\RequirePackage{graphicx}
\RequirePackage{xcolor}
\RequirePackage{booktabs}
\RequirePackage{multirow}
\RequirePackage{array}
\RequirePackage{tabularx}
\RequirePackage{colortbl}
\RequirePackage{bm}
\RequirePackage{placeins}
\RequirePackage{fancyhdr}
\RequirePackage{titlesec}
\RequirePackage{tocloft}
\RequirePackage{caption}
\RequirePackage{subcaption}
\RequirePackage[most]{tcolorbox}
\RequirePackage{hyperref}
\RequirePackage[noabbrev,nameinlink]{cleveref}
\RequirePackage[numbers,sort&compress]{natbib}

\renewcommand{\rmdefault}{ptm}
\renewcommand{\sfdefault}{phv}
\renewcommand{\familydefault}{\rmdefault}


\definecolor{HWRed}{HTML}{C7000B}
\definecolor{TitleRed}{HTML}{B8434A}
\definecolor{ReportBlack}{HTML}{111111}
\definecolor{LinkBlue}{HTML}{1F4E79}
\definecolor{AbstractTint}{HTML}{F3F4F6}
\definecolor{AbstractRule}{HTML}{D7D9DD}

\color{ReportBlack}

\hypersetup{
  colorlinks=true,
  % linkcolor=TitleRed,
  linkcolor=ReportBlack,
  citecolor=TitleRed,
  % citecolor=ReportBlack,
  urlcolor=LinkBlue,
  pdfborder={0 0 0}
}

\def\bibfont{\small}
\renewcommand{\refname}{References}


\makeatletter
\renewcommand{\normalsize}{%
  \@setfontsize\normalsize\@xipt\@xiipt
  \abovedisplayskip 7\p@ \@plus 2\p@ \@minus 5\p@
  \abovedisplayshortskip \z@ \@plus 3\p@
  \belowdisplayskip \abovedisplayskip
  \belowdisplayshortskip 4\p@ \@plus 3\p@ \@minus 3\p@
}
\normalsize
\renewcommand{\small}{%
  \@setfontsize\small\@ixpt\@xpt
  \abovedisplayskip 6\p@ \@plus 1.5\p@ \@minus 4\p@
  \abovedisplayshortskip \z@ \@plus 2\p@
  \belowdisplayskip \abovedisplayskip
  \belowdisplayshortskip 3\p@ \@plus 2\p@ \@minus 2\p@
}
\renewcommand{\footnotesize}{\@setfontsize\footnotesize\@viiipt{9.5}}
\renewcommand{\scriptsize}{\@setfontsize\scriptsize\@viipt\@viiipt}
\renewcommand{\tiny}{\@setfontsize\tiny\@vipt\@viipt}
\renewcommand{\large}{\@setfontsize\large\@xiipt{14}}
\renewcommand{\Large}{\@setfontsize\Large\@xivpt{16}}
\renewcommand{\LARGE}{\@setfontsize\LARGE\@xviipt{20}}
\renewcommand{\huge}{\@setfontsize\huge\@xxpt{23}}
\renewcommand{\Huge}{\@setfontsize\Huge\@xxvpt{28}}
\makeatother

\setlength{\parindent}{0pt}
\setlength{\parskip}{5.5pt}

\newcommand{\sectionfont}{\fontsize{13}{14}\selectfont}
\newcommand{\subsectionfont}{\fontsize{12}{12}\selectfont}
\newcommand{\subsubsectionfont}{\fontsize{11}{12}\selectfont}

% \titleformat*{\section}{\sectionfont\rmfamily\bfseries\color{ReportBlack}}
% \titleformat*{\subsection}{\subsectionfont\rmfamily\bfseries\color{ReportBlack}}
% \titleformat*{\subsubsection}{\subsubsectionfont\rmfamily\bfseries\color{ReportBlack}}
% \titleformat*{\paragraph}{\normalsize\rmfamily\bfseries\color{ReportBlack}}
\titleformat*{\section}{\sectionfont\rmfamily\bfseries\color{TitleRed}}
\titleformat*{\subsection}{\subsectionfont\rmfamily\bfseries\color{TitleRed}}
\titleformat*{\subsubsection}{\subsubsectionfont\rmfamily\bfseries\color{TitleRed}}
\titleformat*{\paragraph}{\normalsize\rmfamily\bfseries\color{ReportBlack}}
\titlespacing*{\paragraph}{0pt}{7pt}{1em} 

\DeclareCaptionLabelSeparator{reportsep}{.\enspace}
\captionsetup{
  font=small,
  labelfont={sf,bf,color=ReportBlack},
  textfont={color=ReportBlack},
  labelsep=reportsep,
  singlelinecheck=true
}
\captionsetup[sub]{font=small,labelfont={sf,bf,color=ReportBlack}}


\setcounter{tocdepth}{3}
\renewcommand{\contentsname}{Contents}
\renewcommand{\cftsecleader}{\cftdotfill{1.8}}
\renewcommand{\cftsubsecleader}{\cftdotfill{1.8}}

% \renewcommand{\cftsecfont}{\rmfamily\bfseries\color{ReportBlack}}
% \renewcommand{\cftsubsecfont}{\rmfamily\color{ReportBlack}}
% \renewcommand{\cftsecpagefont}{\rmfamily\bfseries\color{ReportBlack}}
% \renewcommand{\cftsubsecpagefont}{\rmfamily\color{ReportBlack}}
% \renewcommand{\cfttoctitlefont}{\fontsize{12}{13}\selectfont\rmfamily\bfseries\color{ReportBlack}}

\renewcommand{\cftsecfont}{\normalsize\rmfamily\bfseries\color{ReportBlack}}
\renewcommand{\cftsubsecfont}{\normalsize\rmfamily\color{ReportBlack}}
\renewcommand{\cftsecpagefont}{\normalsize\rmfamily\bfseries\color{ReportBlack}}
\renewcommand{\cftsubsecpagefont}{\normalsize\rmfamily\color{ReportBlack}}



\setlength{\cftbeforesecskip}{6pt}
\setlength{\cftbeforesubsecskip}{4pt}
\setlength{\cftbeforesubsubsecskip}{3pt}
\setlength{\cftsecindent}{0pt}
\setlength{\cftsecnumwidth}{2.6em}
\setlength{\cftsubsecindent}{2.6em}
\setlength{\cftsubsecnumwidth}{3.2em}
\renewcommand{\cftaftertoctitle}{%
  \par\vspace{4pt}%
}


\makeatletter
\let\huawei@originaltableofcontents\tableofcontents
\renewcommand{\tableofcontents}{%
  \begingroup
  \setlength{\parskip}{0pt}%
  \hypersetup{linkcolor=ReportBlack}%
  \huawei@originaltableofcontents
  \endgroup
}

% -----------------------------------------------------------------------------
% Metadata API
% -----------------------------------------------------------------------------
\newcommand{\reporttitle}{Untitled Technical Report}
\renewcommand{\title}[1]{\gdef\reporttitle{#1}}

\newcommand{\reportabstract}{}
\renewcommand{\abstract}[1]{\gdef\reportabstract{#1}}

\newcommand{\authorlist}{}
\newcommand{\reportsuperscript}[1]{\textsuperscript{\normalfont\ensuremath{#1}}}
\newcommand{\authorentry}[2][]{%
  \ifstrempty{#1}{#2}{#2\reportsuperscript{#1}}%
}
\renewcommand{\author}[2][]{%
  \ifdefempty{\authorlist}
    {\gdef\authorlist{\authorentry[#1]{#2}}}
    {\g@addto@macro\authorlist{, \authorentry[#1]{#2}}}%
}

\newcommand{\affiliationlist}{}
\newcommand{\affiliationentry}[2][]{%
  \ifstrempty{#1}{#2}{\reportsuperscript{#1}#2}%
}
\newcommand{\affiliation}[2][]{%
  \ifdefempty{\affiliationlist}
    {\gdef\affiliationlist{\affiliationentry[#1]{#2}}}
    {\g@addto@macro\affiliationlist{; \affiliationentry[#1]{#2}}}%
}

\newcommand{\contributionlist}{}
\newcommand{\contribution}[2][]{%
  \ifdefempty{\contributionlist}
    {\gdef\contributionlist{\affiliationentry[#1]{#2}}}
    {\g@addto@macro\contributionlist{; \affiliationentry[#1]{#2}}}%
}

\newcommand{\metadatalist}{}
\newcommand{\addmetadata}[2]{%
  \ifdefempty{\metadatalist}
    {\gdef\metadatalist{\textbf{#1:} #2}}
    {\g@addto@macro\metadatalist{\quad\textbf{#1:} #2}}%
}
\renewcommand{\date}[1]{\addmetadata{Date}{#1}}
\newcommand{\reportversion}[1]{\addmetadata{Version}{#1}}
\newcommand{\reportstatus}[1]{\addmetadata{Status}{#1}}
\newcommand{\correspondence}[1]{\addmetadata{Correspondence}{#1}}
\newcommand{\email}[1]{\href{mailto:#1}{\texttt{#1}}}

\newcommand{\runningtitletext}{Huawei Cloud Technical Report}
\newcommand{\runningtitle}[1]{\gdef\runningtitletext{#1}}
\newcommand{\reportbrandtext}{Huawei Cloud}
\newcommand{\reportbrand}[1]{\gdef\reportbrandtext{#1}}
\newcommand{\reportlabeltext}{TECHNICAL REPORT}
\newcommand{\reportlabel}[1]{\gdef\reportlabeltext{#1}}


\newcommand{\reportlogopath}{img/huawei-cloudpdf.pdf}%Huawei-Logo-2006.png}
\newcommand{\reportlogo}[1]{\gdef\reportlogopath{#1}}

\newcommand{\reportlogosize}{32mm}
\newcommand{\setreportlogosize}[1]{\gdef\reportlogosize{#1}}
\newcommand{\reportlogoheight}{6.8mm}
\newcommand{\setreportlogoheight}[1]{\gdef\reportlogoheight{#1}}
\newcommand{\reportlogoxshift}{0mm}
\newcommand{\setreportlogoxshift}[1]{\gdef\reportlogoxshift{#1}}
\newcommand{\reportlogoraise}{0mm}
\newcommand{\setreportlogoraise}[1]{\gdef\reportlogoraise{#1}}

\newcommand{\reportlogoyshift}{\reportlogoraise}
\newcommand{\setreportlogoyshift}[1]{\gdef\reportlogoraise{#1}}

\newcommand{\reportfirstpagecontent}{}
\newcommand{\reportfirstpage}[1]{\gdef\reportfirstpagecontent{#1}}
\newcommand{\reportteasercontent}{}
\newcommand{\reportteaserheight}{72mm}
\newcommand{\setreportteaserheight}[1]{\gdef\reportteaserheight{#1}}
\newcommand{\reportteaser}[2][]{%
  \gdef\reportteasercontent{%
    \begin{center}%
      \includegraphics[width=\linewidth,height=\reportteaserheight,keepaspectratio]{#2}%
      \ifstrempty{#1}{}{\par\vspace{1.5mm}{\small\itshape #1}}%
    \end{center}%
  }%
}
\newcommand{\reporthighlightcontent}{}
\newcommand{\reporthighlights}[6]{%
  \gdef\reporthighlightcontent{%
    \noindent{\rmfamily\bfseries\fontsize{11}{13}\selectfont Report at a glance\par}%
    \vspace{2mm}%
    {\color{ReportBlack}\hrule height 0.45pt}%
    \vspace{3mm}%
    \begin{tabularx}{\linewidth}{@{}>{\raggedright\arraybackslash}X@{\hspace{5mm}}>{\raggedright\arraybackslash}X@{\hspace{5mm}}>{\raggedright\arraybackslash}X@{}}%
      {\rmfamily\bfseries\color{HWRed}#1} & {\rmfamily\bfseries\color{HWRed}#3} & {\rmfamily\bfseries\color{HWRed}#5} \\[1.5mm]%
      {\small #2} & {\small #4} & {\small #6}%
    \end{tabularx}%
    \vspace{3mm}%
    {\color{ReportBlack}\hrule height 0.45pt}%
  }%
}

% Title-page typography
\newcommand{\reporttitlefont}{\fontsize{17}{20}\selectfont}
\newcommand{\reportauthorfont}{\fontsize{12}{14}\selectfont}
\newcommand{\reportaffiliationfont}{\fontsize{11}{13}\selectfont}
\newcommand{\reportmetafont}{\fontsize{8}{10}\selectfont}
\newcommand{\reportabstractfont}{\fontsize{10}{12}\selectfont}


\setlength{\headheight}{16pt}


\fancypagestyle{firststyle}{%
  \fancyhf{}
  \renewcommand{\headrulewidth}{0pt}
  \renewcommand{\footrulewidth}{0pt}
}


\fancypagestyle{mainstyle}{%
  \fancyhf{}
  \fancyfoot[C]{\rmfamily\fontsize{8}{10}\selectfont\color{ReportBlack}\thepage}
  \renewcommand{\headrulewidth}{0pt}
  \renewcommand{\footrulewidth}{0pt}
}
\pagestyle{mainstyle}


\newcommand{\makehuaweitoprow}{%
  \noindent

  \begin{minipage}[t]{0.50\linewidth}
    \vspace{0pt}% make the outer minipage top-aligned
    \begin{minipage}[t][\reportlogoheight][s]{\linewidth}
      \vspace{0pt}%
      {\sffamily\bfseries\fontsize{9.5}{11.5}\selectfont
       \color{HWRed}\reportlabeltext\par}%
      \vfill
      {\color{HWRed}\rule{26mm}{0.75pt}\par}%
    \end{minipage}%
  \end{minipage}%
  \hfill
  \begin{minipage}[t]{0.46\linewidth}
    \vspace{0pt}% make the logo box share the same top edge
    \raggedleft
    \IfFileExists{\reportlogopath}{%
      \hspace*{\reportlogoxshift}%
      \raisebox{\reportlogoraise}{%
        \includegraphics[
          width=\reportlogosize,
          height=\reportlogoheight,
          keepaspectratio
        ]{\reportlogopath}%
      }%
    }{%
      \begin{minipage}[t][\reportlogoheight][t]{\linewidth}
        \vspace{0pt}\raggedleft
        {\sffamily\bfseries\fontsize{10}{12}\selectfont
         \color{HWRed}\reportbrandtext\strut}%
      \end{minipage}%
    }%
  \end{minipage}%
}



\newcommand{\makehuaweiheader}{%
  \begingroup
  \setlength{\parindent}{0pt}
  \setlength{\parskip}{0pt}

  % The label, logo, and short accent rule form one aligned brand row.
  \makehuaweitoprow
  \vspace{7mm}

  {\reporttitlefont\rmfamily\bfseries\color{ReportBlack}\RaggedRight\sloppy\nohyphens\reporttitle\par}
  \vspace{6mm}

  {\reportauthorfont\rmfamily\color{ReportBlack}\authorlist\par}
  \vspace{3mm}
  {\reportaffiliationfont\rmfamily\color{ReportBlack}\affiliationlist\par}
  \ifdefempty{\contributionlist}{}{%
    \vspace{3mm}
    {\reportaffiliationfont\color{ReportBlack}\contributionlist\par}%
  }

  \vspace{6mm}

  \begin{tcolorbox}[
    enhanced,
    colback=AbstractTint,
    colframe=AbstractRule,
    boxrule=0.35pt,
    arc=1.2mm,
    grow to left by=6mm,
    grow to right by=6mm,
    left=5mm,right=5mm,top=3mm,bottom=3mm,
    before skip=0pt,after skip=0pt
  ]
    {\rmfamily\bfseries\fontsize{10}{12}\selectfont\color{HWRed}Abstract\par}
    \vspace{3mm}
    {\reportabstractfont\color{ReportBlack}\reportabstract\par}
    \ifdefempty{\metadatalist}{}{%
      \vspace{3mm}
      {\reportmetafont\rmfamily\color{ReportBlack}\metadatalist\par}%
    }
  \end{tcolorbox}

  \ifdefempty{\reportteasercontent}{}{\vspace{7mm}\reportteasercontent}%
  \ifdefempty{\reporthighlightcontent}{}{\vspace{7mm}\reporthighlightcontent}%
  \ifdefempty{\reportfirstpagecontent}{}{\vspace{7mm}\reportfirstpagecontent}%
  \endgroup
  \FloatBarrier
  \thispagestyle{firststyle}
}

\if@twocolumn
  \renewcommand{\maketitle}{%
    \twocolumn[\vskip 3mm\makehuaweiheader\vspace{8mm}]%
    \pagestyle{mainstyle}%
  }
\else
  \renewcommand{\maketitle}{%
    \vskip 3mm
    \makehuaweiheader
    \vspace{8mm}
    \pagestyle{mainstyle}%
  }
\fi


\newcommand{\makereportfrontmatter}{%
  \maketitle
  \clearpage
  \tableofcontents
  \clearpage
}

% -----------------------------------------------------------------------------
% Convenience commands
% -----------------------------------------------------------------------------
\newcommand{\best}[1]{\textbf{#1}}
\newcommand{\secondbest}[1]{\underline{#1}}
\newcommand{\ours}[1]{\textcolor{HWRed}{\textbf{#1}}}
\newcommand{\hwtablehead}{\rowcolor{white}}
\newcommand{\hwthead}[1]{\textbf{#1}}
\newcommand{\reportaccent}[1]{\textcolor{HWRed}{#1}}
\newcommand{\redref}[1]{{\hypersetup{linkcolor=TitleRed}\ref{#1}}}

% White-background callouts only; no gray panels beyond the abstract.
\newtcolorbox{reportkeybox}[1][]{%
  enhanced,
  colback=white,
  colframe=white,
  boxrule=0pt,
  arc=0mm,
  borderline west={1.5pt}{0pt}{HWRed},
  left=4mm,right=1mm,top=1.7mm,bottom=1.7mm,
  before skip=6pt,after skip=6pt,
  fonttitle=\sffamily\bfseries\small,
  coltitle=HWRed,
  colbacktitle=white,
  attach title to upper={\par\vspace{1.2mm}},
  title=#1
}

\newtcolorbox{reportnotebox}[1][]{%
  enhanced,
  colback=white,
  colframe=ReportBlack,
  boxrule=0.35pt,
  arc=0.7mm,
  left=4mm,right=4mm,top=3mm,bottom=3mm,
  before skip=6pt,after skip=6pt,
  fonttitle=\sffamily\bfseries\small,
  coltitle=ReportBlack,
  colbacktitle=white,
  attach title to upper={\par\vspace{1.2mm}},
  title=#1
}

\newcommand{\beginappendix}{%
  \appendix
  \section*{Appendix}
  \addcontentsline{toc}{section}{Appendix}%
}

\makeatother
